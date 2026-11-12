#!/usr/bin/env python3
"""
Builds catalog.json for the Data Removal app.

Inputs:
  sources/curated.json   hand-prepared sources (priority sites, channel, fields, notes)
  sources/laws.json      law profiles with request / follow-up / complaint templates
  sources/overrides.json optional corrections by source id, applied last (for example a search address
                         checked on a phone: {"spokeo": {"searchUrl": "https://..."}}); null removes a field
  --optery PATH          data-brokers.json from github.com/optery/optery-data-brokers-directory
                         (people-search sites not in the curated list are added as "listed")
  --ddg DIR              broker definitions from DuckDuckGo's Personal Information Removal
                         (github.com/duckduckgo/Android, pir/pir-impl/src/main/assets/brokers, Apache 2.0):
                         search-address templates, opt-out pages, the fields each opt-out form asks for,
                         email confirmation and CAPTCHA flags. Sites it describes become "prepared".

Usage: python3 tools/build_catalog.py --optery data-brokers.json [--ddg DIR] --out catalog.json [--version N]
The output is deterministic for the same inputs and version, so the signature only changes when content does.
"""
import argparse
import json
import re
import sys
import time
from urllib.parse import urlparse

SCHEMA_VERSION = 1
CHANNELS = {"email", "web_form", "guided", "phone_mail"}
FIELDS = {"full_name", "email", "phone", "address", "city_state", "birth_date", "birth_year", "profile_url", "id_document"}
# "unknown": nobody has looked yet. Never shown as "no verification needed".
VERIFICATIONS = {"none", "unknown", "email_link", "phone_code", "phone_call", "id_document"}
FLAGS = {"asks_birth_date", "captcha", "may_ask_id", "may_require_phone_call", "needs_account", "one_optout_per_email",
         "paid_access", "phone_code", "removal_via_parent", "search_from_ddg"}
# Variables and modifiers a search-address template may use (same syntax as DuckDuckGo's definitions).
SEARCH_VARS = {"firstName", "lastName", "middleName", "city", "state", "age"}
SEARCH_MODS = {"hyphenated", "upcase", "downcase", "capitalize", "stateFull", "ageRange", "defaultIfEmpty", "replaceWhitespace"}
TEMPLATE_PART = re.compile(r"\$\{([^}]+)\}")
CONFIDENCE = {"tested", "untested", "listed", "defunct"}
CATEGORIES = {"people_search", "marketing", "b2b", "phone_directory", "other"}


def domain(url):
    host = urlparse(url if "://" in url else "https://" + url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# Values the app always has when it writes a letter. Any other value may be missing, and the app then
# drops the whole line that holds it, so such a value must sit on its own short "Label: {{value}}" line,
# never inside a sentence that would vanish with it.
ALWAYS_PRESENT = {"full_name", "source_name", "date", "source_website", "citation", "response_days"}
PLACEHOLDER = re.compile(r"\{\{([a-z_]+)\}\}")


def check_template_lines(law_id, kind, t):
    for p in PLACEHOLDER.findall(t["subject"]):
        if p not in ALWAYS_PRESENT:
            fail(f"law {law_id}: {kind} subject uses {p}, which may be missing")
    for line in t["body"].split("\n"):
        optional = [p for p in PLACEHOLDER.findall(line) if p not in ALWAYS_PRESENT]
        if not optional:
            continue
        rest = PLACEHOLDER.sub("", line).strip()
        if len(optional) > 1 or len(rest) > 40 or not (rest == "" or rest.endswith(":")):
            fail(f"law {law_id}: {kind} line must be 'Label: {{{{value}}}}': {line!r}")


def check_source(s):
    for key in ("id", "name", "website", "category", "channel", "requiredFields", "verification", "confidence"):
        if key not in s:
            fail(f"{s.get('id', '?')}: missing {key}")
    if s["channel"] not in CHANNELS:
        fail(f"{s['id']}: bad channel {s['channel']}")
    if s["category"] not in CATEGORIES:
        fail(f"{s['id']}: bad category {s['category']}")
    if s["verification"] not in VERIFICATIONS:
        fail(f"{s['id']}: bad verification {s['verification']}")
    if s["confidence"] not in CONFIDENCE:
        fail(f"{s['id']}: bad confidence {s['confidence']}")
    bad = set(s["requiredFields"]) - FIELDS
    if bad:
        fail(f"{s['id']}: unknown fields {sorted(bad)}")
    for key in ("website", "optOutUrl", "searchUrl"):
        if s.get(key) and not s[key].startswith("https://"):
            fail(f"{s['id']}: {key} must be https")
    bad_flags = set(s.get("flags", [])) - FLAGS
    if bad_flags:
        fail(f"{s['id']}: unknown flags {sorted(bad_flags)}")
    if s["confidence"] == "tested" and not s.get("testedOn"):
        fail(f"{s['id']}: a tested source needs testedOn (the date of the documented test)")
    if s["channel"] == "email" and not s.get("email"):
        fail(f"{s['id']}: email channel without an email address")
    if s["channel"] == "web_form" and not s.get("optOutUrl"):
        fail(f"{s['id']}: web_form channel without optOutUrl")
    for part in TEMPLATE_PART.findall(s.get("searchUrl", "")):
        var, *mods = part.split("|")
        if var not in SEARCH_VARS:
            fail(f"{s['id']}: searchUrl uses unknown variable {var}")
        for m in mods:
            if m.split(":")[0] not in SEARCH_MODS:
                fail(f"{s['id']}: searchUrl uses unknown modifier {m}")
        if "ageRange" in mods and not s.get("searchAgeRanges"):
            fail(f"{s['id']}: ageRange without searchAgeRanges")


def from_optery(entry):
    name = (entry.get("title") or entry.get("name") or "").strip()
    website = (entry.get("website") or entry.get("url") or "").strip()
    if website and not website.startswith("http"):
        website = "https://" + website
    website = website.replace("http://", "https://")
    opt_out = entry.get("opt_out_url", "").strip().replace("http://", "https://")
    email = entry.get("email", "").strip()
    channel = "web_form" if opt_out else ("email" if email else "guided")
    s = {
        "id": slug(domain(website) or name),
        "name": name,
        "website": website,
        "category": "people_search",
        "channel": channel,
        "requiredFields": ["full_name"],
        "verification": "unknown",
        "confidence": "listed",
    }
    if opt_out.startswith("https://"):
        s["optOutUrl"] = opt_out
    if email and "@" in email:
        s["email"] = email
    return s


DDG_FIELDS = {
    "email": "email", "profileUrl": "profile_url", "fullName": "full_name", "firstName": "full_name",
    "lastName": "full_name", "middleName": "full_name", "city": "city_state", "state": "city_state",
    "fullState": "city_state", "age": "birth_year", "birthYear": "birth_year",
}


def load_ddg(folder):
    """Reads DuckDuckGo's broker definitions into {domain: facts}."""
    import glob
    import os
    out = {}
    for path in sorted(glob.glob(os.path.join(folder, "*.json"))):
        d = json.load(open(path, encoding="utf-8"))
        dom = domain(d.get("url", ""))
        if not dom:
            continue
        facts = {"name": d.get("name") or dom, "domain": dom, "optOutUrl": d.get("optOutUrl"), "parent": d.get("parent"),
                 "fields": set(), "verification": "unknown", "flags": set(), "searchUrl": None, "ageRanges": None, "viaParent": False}
        for step in d.get("steps", []):
            actions = step.get("actions", [])
            if step.get("stepType") == "scan":
                for a in actions:
                    url = a.get("url", "")
                    if a.get("actionType") == "navigate" and "${" in url and url.startswith("https://") and facts["searchUrl"] is None:
                        facts["searchUrl"] = url
                        facts["ageRanges"] = a.get("ageRange")
            elif step.get("stepType") == "optOut":
                if step.get("optOutType") == "parentSiteOptOut":
                    facts["viaParent"] = True
                kinds = {a.get("actionType") for a in actions}
                if "emailConfirmation" in kinds:
                    facts["verification"] = "email_link"
                elif actions:
                    facts["verification"] = "none"
                if "getCaptchaInfo" in kinds or "solveCaptcha" in kinds:
                    facts["flags"].add("captcha")
                for a in actions:
                    for e in a.get("elements") or []:
                        f = DDG_FIELDS.get(e.get("type"))
                        if f:
                            facts["fields"].add(f)
        # Templates with variables this app does not know are left out rather than half-filled.
        if facts["searchUrl"]:
            for part in TEMPLATE_PART.findall(facts["searchUrl"]):
                var, *mods = part.split("|")
                if var not in SEARCH_VARS or any(m.split(":")[0] not in SEARCH_MODS for m in mods):
                    facts["searchUrl"] = None
                    break
        out[dom] = facts
    return out


def apply_ddg(s, facts, ddg, prepared):
    """Adds DuckDuckGo's facts to a source. Curated sources keep their own channel, fields and notes."""
    if facts["searchUrl"]:
        s["searchUrl"] = facts["searchUrl"]
        if facts["ageRanges"]:
            s["searchAgeRanges"] = facts["ageRanges"]
        s["flags"] = sorted(set(s.get("flags", [])) | {"search_from_ddg"})
    if not prepared:
        return
    opt_out = facts["optOutUrl"]
    parent = ddg.get(domain(facts["parent"] or "")) if facts["viaParent"] else None
    if parent:
        opt_out = parent["optOutUrl"] or opt_out
        s["owner"] = parent["name"]
        s["flags"] = sorted(set(s.get("flags", [])) | {"removal_via_parent"})
        s["notes"] = f"Removal goes through {parent['name']} ({parent['domain']}); one request there covers this site."
        fields, verification, flags = parent["fields"], parent["verification"], parent["flags"]
    else:
        fields, verification, flags = facts["fields"], facts["verification"], facts["flags"]
    if not opt_out or not opt_out.startswith("https://"):
        return
    s["channel"] = "web_form"
    s["optOutUrl"] = opt_out
    s["requiredFields"] = sorted(fields or {"full_name"})
    s["verification"] = verification
    s["flags"] = sorted(set(s.get("flags", [])) | flags)
    s["confidence"] = "untested"


def next_version(requested, previous_path="catalog.json"):
    """Strictly increasing, so two publishes in the same second still get different numbers."""
    try:
        previous = json.load(open(previous_path, encoding="utf-8")).get("version", 0)
    except (OSError, ValueError):
        previous = 0
    return requested if requested > previous else previous + 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--optery", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--ddg")
    p.add_argument("--version", type=int, default=None)
    a = p.parse_args()
    if a.version is None:
        a.version = next_version(int(time.strftime("%Y%m%d%H%M%S", time.gmtime())))
    ddg = load_ddg(a.ddg) if a.ddg else {}

    curated = json.load(open("sources/curated.json", encoding="utf-8"))
    laws = json.load(open("sources/laws.json", encoding="utf-8"))
    optery = json.load(open(a.optery, encoding="utf-8"))

    sources = []
    seen_ids, seen_domains = set(), set()
    for s in curated:
        s = dict(s)
        s.setdefault("confidence", "untested")
        s.setdefault("relistDays", 90)
        f = ddg.get(domain(s["website"]))
        if f:
            apply_ddg(s, f, ddg, prepared=False)
        check_source(s)
        if s["id"] in seen_ids:
            fail(f"duplicate id {s['id']}")
        seen_ids.add(s["id"])
        seen_domains.add(domain(s["website"]))
        sources.append(s)

    added = 0
    for entry in sorted(optery, key=lambda e: (e.get("title") or e.get("name") or "").lower()):
        if entry.get("type") != "People Search Site" or not (entry.get("website") or entry.get("url")):
            continue
        s = from_optery(entry)
        d = domain(s["website"])
        if not s["id"] or not s["website"].startswith("https://") or d in seen_domains or s["id"] in seen_ids:
            continue
        s["relistDays"] = 90
        if d in ddg:
            apply_ddg(s, ddg[d], ddg, prepared=True)
        check_source(s)
        seen_ids.add(s["id"])
        seen_domains.add(d)
        sources.append(s)
        added += 1

    # Sites DuckDuckGo describes that neither list has yet.
    ddg_added = 0
    for d, f in sorted(ddg.items()):
        if d in seen_domains:
            continue
        s = {"id": slug(d), "name": f["name"], "website": "https://" + d, "category": "people_search", "channel": "guided",
             "requiredFields": ["full_name"], "verification": "unknown", "confidence": "listed", "relistDays": 90}
        apply_ddg(s, f, ddg, prepared=True)
        if s["id"] in seen_ids or (s["channel"] == "guided" and "searchUrl" not in s):
            continue
        check_source(s)
        seen_ids.add(s["id"])
        seen_domains.add(d)
        sources.append(s)
        ddg_added += 1

    # Corrections found by testing on a real phone win over every other input.
    try:
        overrides = json.load(open("sources/overrides.json", encoding="utf-8"))
    except FileNotFoundError:
        overrides = {}
    by_id = {x["id"]: x for x in sources}
    for sid, changes in overrides.items():
        if sid not in by_id:
            fail(f"overrides.json: unknown source {sid}")
        for k, v in changes.items():
            if v is None:
                by_id[sid].pop(k, None)
            else:
                by_id[sid][k] = v
        check_source(by_id[sid])

    for law in laws:
        if not 7 <= law["responseDays"] <= 365:
            fail(f"law {law['id']}: responseDays must be 7..365")
        for kind in ("request", "followUp", "complaint"):
            t = law["templates"][kind]
            if not t["subject"] or not t["body"]:
                fail(f"law {law['id']}: empty {kind} template")
            check_template_lines(law["id"], kind, t)
    if not any(l["id"] == "GENERIC" for l in laws):
        fail("GENERIC law profile is required")

    catalog = {
        "schemaVersion": SCHEMA_VERSION,
        "version": a.version,
        "attribution": [
            "Optery Data Brokers Directory — https://github.com/optery/optery-data-brokers-directory (CC BY-NC-SA 4.0)",
            "Big Ass Data Broker Opt-Out List (BADBOOL) — https://github.com/yaelwrites/Big-Ass-Data-Broker-Opt-Out-List (CC BY-NC-SA)",
        ] + (["DuckDuckGo Personal Information Removal broker definitions — https://github.com/duckduckgo/Android (Apache License 2.0; search addresses, opt-out pages and form fields, adapted)"] if ddg else []),
        "laws": laws,
        "sources": sources,
    }
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    prepared = sum(1 for x in sources if x["confidence"] in ("untested", "tested"))
    searchable = sum(1 for x in sources if "${" in x.get("searchUrl", ""))
    print(f"catalog v{a.version}: {len(curated)} curated + {added} from Optery + {ddg_added} from DuckDuckGo = {len(sources)} sources; "
          f"{prepared} prepared, {searchable} with a direct search address; {len(laws)} law profiles")


if __name__ == "__main__":
    main()

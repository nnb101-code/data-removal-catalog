#!/usr/bin/env python3
"""
Builds catalog.json for the Data Removal app.

Inputs:
  sources/curated.json   hand-prepared sources (priority sites, channel, fields, notes)
  sources/laws.json      law profiles with request / follow-up / complaint templates
  --optery PATH          data-brokers.json from github.com/optery/optery-data-brokers-directory
                         (people-search sites not in the curated list are added as "listed")

Usage: python3 tools/build_catalog.py --optery data-brokers.json --out catalog.json [--version N]
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
VERIFICATIONS = {"none", "email_link", "phone_code", "phone_call", "id_document"}
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
        "verification": "none",
        "confidence": "listed",
    }
    if opt_out.startswith("https://"):
        s["optOutUrl"] = opt_out
    if email and "@" in email:
        s["email"] = email
    return s


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--optery", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--version", type=int, default=int(time.strftime("%Y%m%d%H%M", time.gmtime())))
    a = p.parse_args()

    curated = json.load(open("sources/curated.json", encoding="utf-8"))
    laws = json.load(open("sources/laws.json", encoding="utf-8"))
    optery = json.load(open(a.optery, encoding="utf-8"))

    sources = []
    seen_ids, seen_domains = set(), set()
    for s in curated:
        s = dict(s)
        s.setdefault("confidence", "untested")
        s.setdefault("relistDays", 90)
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
        check_source(s)
        seen_ids.add(s["id"])
        seen_domains.add(d)
        sources.append(s)
        added += 1

    for law in laws:
        if not 7 <= law["responseDays"] <= 365:
            fail(f"law {law['id']}: responseDays must be 7..365")
        for kind in ("request", "followUp", "complaint"):
            t = law["templates"][kind]
            if not t["subject"] or not t["body"]:
                fail(f"law {law['id']}: empty {kind} template")
    if not any(l["id"] == "GENERIC" for l in laws):
        fail("GENERIC law profile is required")

    catalog = {
        "schemaVersion": SCHEMA_VERSION,
        "version": a.version,
        "attribution": [
            "Optery Data Brokers Directory — https://github.com/optery/optery-data-brokers-directory (CC BY-NC-SA 4.0)",
            "Big Ass Data Broker Opt-Out List (BADBOOL) — https://github.com/yaelwrites/Big-Ass-Data-Broker-Opt-Out-List (CC BY-NC-SA)",
        ],
        "laws": laws,
        "sources": sources,
    }
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print(f"catalog v{a.version}: {len(curated)} curated + {added} listed = {len(sources)} sources, {len(laws)} law profiles")


if __name__ == "__main__":
    main()

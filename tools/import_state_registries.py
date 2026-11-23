#!/usr/bin/env python3
"""
Turns the Texas, Vermont and Oregon data broker registries into sources/state-registries.json:
one entry per registered broker with its official contact email.

Why not the state websites themselves: the Texas registry (Appian portal) and the Vermont registry
(bizfilings) only show results to a browser behind reCAPTCHA, and Oregon's daily licence file has no
email or website. So the input is the merged registry file that Privacy Rights Clearinghouse built from
the five state registries (CC BY-NC-SA 4.0, same licence as this catalog):
  https://privacyrights.org/sites/default/files/2025-05/Data_Broker_Full_Registry_2025.xlsx.xlsx
Rows of one broker share a GroupUUID_Combined, so a Texas row with no website borrows it from the same
broker's Vermont or California row. When no row has a website, the email's domain stands in for it
(never a free-mail domain such as gmail.com).

Every broker here is legally registered as a data broker in at least one of the three states, so each is
a target for the app's general deletion email (channel "email", nothing to search). The builder skips any
broker another input already has (same domain or same email).

Usage:    python3 tools/import_state_registries.py Data_Broker_Full_Registry_2025.xlsx [--out sources/state-registries.json]
Needs:    pip install openpyxl
The output is sorted and stable, so it only changes when the input does.
"""
import argparse
import collections
import json
import re
import sys
from urllib.parse import urlparse

STATES = {"Texas": "TX", "Vermont": "VT", "Oregon": "OR"}
EMAIL = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
FREE_MAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com", "me.com", "msn.com",
             "live.com", "protonmail.com", "proton.me", "comcast.net", "att.net", "verizon.net", "ymail.com", "gmx.com"}
NEEDED = ("GroupUUID_Combined", "Name", "RegistrySource", "WebsiteURL", "OptOutURL", "Email")


def domain(url):
    url = str(url or "").strip()
    url = url.split()[0] if url else ""
    host = urlparse(url if "://" in url else "https://" + url).netloc.lower().split(":")[0].strip(".")
    return host[4:] if host.startswith("www.") else host


def emails(text):
    out = []
    for m in EMAIL.findall(str(text or "")):
        m = m.strip(".").lower()
        # A registry contact at a government address is the registry, not the broker.
        if not m.endswith(".gov") and m not in out:
            out.append(m)
    return out


def clean(text):
    return re.sub(r"\s+", " ", str(text or "").strip())


def https_page(url):
    url = clean(url).split(" ")[0] if clean(url) else ""
    if not url:
        return None
    if not url.startswith("http"):
        url = "https://" + url
    url = url.replace("http://", "https://", 1)
    return url if "." in domain(url) else None


def convert(rows):
    """rows: dicts with the NEEDED columns. Returns sorted broker entries for TX/VT/OR registrations."""
    groups = collections.defaultdict(list)
    for r in rows:
        gid = clean(r.get("GroupUUID_Combined")) or "name:" + clean(r.get("Name")).lower()
        groups[gid].append(r)
    by_domain = {}
    for gid in sorted(groups):
        rs = groups[gid]
        states = sorted({STATES[clean(r.get("RegistrySource"))] for r in rs if clean(r.get("RegistrySource")) in STATES})
        if not states:
            continue  # only registered in California: sources/ca-registry.json covers it
        # Emails from the three states' rows first, most frequent wins; ties: alphabetical (stable output).
        counts = collections.Counter()
        for r in rs:
            if clean(r.get("RegistrySource")) in STATES:
                counts.update(emails(r.get("Email")))
        if not counts:
            continue
        email = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        sites = collections.Counter(d for d in (domain(r.get("WebsiteURL")) for r in rs) if "." in d)
        dom = sorted(sites.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if sites else ""
        if not dom:
            mail_dom = email.split("@", 1)[1]
            if mail_dom in FREE_MAIL:
                continue
            dom = mail_dom[4:] if mail_dom.startswith("www.") else mail_dom
        names = collections.Counter(clean(r.get("Name")) for r in rs if clean(r.get("Name")))
        name = sorted(names.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if names else dom
        entry = {"name": name[:120], "domain": dom, "email": email, "states": states}
        for r in rs:
            page = https_page(r.get("OptOutURL"))
            if page:
                entry["privacyPage"] = page
                break
        old = by_domain.get(dom)
        if old:  # two groups, one website: keep one entry, all states
            old["states"] = sorted(set(old["states"]) | set(states))
            continue
        by_domain[dom] = entry
    return sorted(by_domain.values(), key=lambda e: e["domain"])


def read_xlsx(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb["Data Brokers"] if "Data Brokers" in wb.sheetnames else wb.worksheets[0]
    it = ws.iter_rows(values_only=True)
    header = [clean(h) for h in next(it)]
    missing = [c for c in NEEDED if c not in header]
    if missing:
        raise ValueError(f"missing columns: {', '.join(missing)}")
    return [dict(zip(header, r)) for r in it]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("xlsx")
    p.add_argument("--out", default="sources/state-registries.json")
    a = p.parse_args()
    try:
        rows = read_xlsx(a.xlsx)
    except Exception as e:  # a broken download must never wipe the committed list
        print(f"ERROR: cannot read {a.xlsx}: {e}; nothing written", file=sys.stderr)
        sys.exit(1)
    brokers = convert(rows)
    if len(brokers) < 100:
        print(f"ERROR: only {len(brokers)} brokers read; nothing written", file=sys.stderr)
        sys.exit(1)
    doc = {"source": "Texas, Vermont and Oregon data broker registries, merged by Privacy Rights Clearinghouse "
                     "(CC BY-NC-SA 4.0) — https://privacyrights.org/resources-tools/reports/why-are-hundreds-data-brokers-not-registering-states",
           "brokers": brokers}
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    per = collections.Counter(s for b in brokers for s in b["states"])
    print(f"{len(brokers)} brokers registered in TX/VT/OR with a contact email written to {a.out} "
          f"(TX {per['TX']}, VT {per['VT']}, OR {per['OR']})")


if __name__ == "__main__":
    main()

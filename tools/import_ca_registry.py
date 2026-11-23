#!/usr/bin/env python3
"""
Turns the California Data Broker Registry (CalPrivacy / CPPA, public government data) into
sources/ca-registry.json: one entry per registered broker with its official contact email.

Every broker on this list is legally registered as a data broker, so each one is a target for the
app's general deletion email (channel "email", nothing to search). The builder skips any broker that
another input already has (same website domain or same email), so curated and prepared sites keep
their own data.

Download: https://cppa.ca.gov/data_broker_registry/registry.csv
Usage:    python3 tools/import_ca_registry.py registry.csv [--out sources/ca-registry.json]
The output is sorted and stable, so it only changes when the registry does.
"""
import argparse
import csv
import json
import re
import sys
from urllib.parse import urlparse

EMAIL = re.compile(r"^[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
COL_NAME = "Data broker name:"
COL_DBA = "Doing Business As (DBA), if applicable:"
COL_SITE = "Data broker primary website:"
COL_EMAIL = "Data broker primary contact email address:"
COL_RIGHTS = "Data broker's primary website that contains details on how consumers can exercise their CA Consumer Privacy rights:"
EMPTY = {"", "n/a", "na", "none", "not applicable", "-"}


def domain(url):
    url = (url or "").strip().split()[0] if (url or "").strip() else ""
    host = urlparse(url if "://" in url else "https://" + url).netloc.lower()
    host = host.split(":")[0]
    return host[4:] if host.startswith("www.") else host


def first_email(text):
    for part in re.split(r"[\s,;/]+", (text or "").strip()):
        part = part.strip("<>()[]\"'.").lower()
        if EMAIL.match(part):
            return part
    return None


def clean(text):
    text = re.sub(r"\s+", " ", (text or "").strip())
    return "" if text.lower() in EMPTY else text


def convert(rows):
    out, seen = [], set()
    for r in rows:
        name, dba = clean(r.get(COL_NAME)), clean(r.get(COL_DBA))
        dom = domain(r.get(COL_SITE))
        email = first_email(r.get(COL_EMAIL))
        if not name or not email or not dom or "." not in dom:
            continue
        if dom in seen:
            continue
        seen.add(dom)
        # A short trade name reads better first; a long list of trade names would flood the screen.
        show = f"{dba} ({name})" if dba and dba.lower() != name.lower() and len(dba) <= 40 else name
        entry = {"name": show[:120], "domain": dom, "email": email}
        rights = clean(r.get(COL_RIGHTS))
        if rights:
            rights = rights.split()[0]
            if not rights.startswith("http"):
                rights = "https://" + rights
            rights = rights.replace("http://", "https://")
            if domain(rights):
                entry["privacyPage"] = rights
        out.append(entry)
    return sorted(out, key=lambda e: e["domain"])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv")
    p.add_argument("--out", default="sources/ca-registry.json")
    a = p.parse_args()
    with open(a.csv, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows or COL_EMAIL not in rows[0] or COL_SITE not in rows[0]:
        print("ERROR: the registry file does not have the expected columns; nothing written", file=sys.stderr)
        sys.exit(1)
    brokers = convert(rows)
    # A broken download must never wipe the list: a real registry has hundreds of brokers.
    if len(brokers) < 100:
        print(f"ERROR: only {len(brokers)} brokers read; nothing written", file=sys.stderr)
        sys.exit(1)
    doc = {"source": "California Data Broker Registry (CalPrivacy) — https://cppa.ca.gov/data_broker_registry/", "brokers": brokers}
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print(f"{len(brokers)} registered brokers with a contact email written to {a.out}")


if __name__ == "__main__":
    main()

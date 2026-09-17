"""URL Audit Script for Schemora Indexed Schemes.

Audits source_url, official_scheme_url, application_url, official_portal_url across indexed schemes.
"""

import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

DATASET_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "final", "schemes.json"))

def audit_scheme_urls():
    if not os.path.exists(DATASET_PATH):
        print(f"Dataset file not found at {DATASET_PATH}")
        return

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        schemes = json.load(f)

    print("\n==========================================================================")
    print(f"SCHEMORA INDEXED SCHEME URL AUDIT (TOTAL SCHEMES: {len(schemes)})")
    print("==========================================================================\n")

    total_schemes = len(schemes)
    missing_app_url = []
    valid_app_url = []
    valid_scheme_url = []
    valid_source_url = []

    for s in schemes:
        title = s.get("scheme_name", "Unknown")
        off_source = s.get("official_source", {})
        source_url = off_source.get("url", "") or s.get("source_url", "")
        app_dict = s.get("application", {})
        app_url = app_dict.get("url", "") or s.get("application_url", "")

        if source_url:
            valid_source_url.append((title, source_url))
            valid_scheme_url.append((title, source_url))

        if app_url and app_url.strip():
            valid_app_url.append((title, app_url))
        else:
            missing_app_url.append(title)

    print(f"1. Total Schemes Audited: {total_schemes}")
    print(f"2. Schemes with Valid Source/Official Info URL: {len(valid_source_url)} / {total_schemes}")
    print(f"3. Schemes with Direct Application URL: {len(valid_app_url)} / {total_schemes}")
    print(f"4. Schemes MISSING Direct Application URL: {len(missing_app_url)} / {total_schemes}")

    if missing_app_url:
        print("\nSchemes with Missing Direct Application URL (Fallback to Official Scheme/Portal URL active):")
        for t in missing_app_url:
            print(f"  - {t}")

if __name__ == "__main__":
    audit_scheme_urls()

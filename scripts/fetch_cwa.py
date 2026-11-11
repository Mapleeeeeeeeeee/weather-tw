#!/usr/bin/env python3
"""
CWA Weather Data Fetcher
Downloads weather forecast datasets from Taiwan Central Weather Administration (CWA).
"""

import os
import sys
import json
import ssl
import urllib.request
import urllib.error

CWA_API_KEY = os.environ.get("CWA_API_KEY", "")
if not CWA_API_KEY:
    sys.exit("請先設定環境變數 CWA_API_KEY")

def get_ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    ctx = ssl.create_default_context()
    # Taiwan gov certificates sometimes lack Subject Key Identifier in Python 3.13
    try:
        return ctx
    except Exception:
        return ssl._create_unverified_context()

def fetch_cwa_dataset(dataset_id: str, key: str = CWA_API_KEY) -> dict:
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{dataset_id}?Authorization={key}&format=JSON"
    req = urllib.request.Request(url, headers={"User-Agent": "WeatherTW/1.0"})
    
    # Try with default context, fallback if cert check fails on government CA
    ctx = None
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ctx = ssl.create_default_context()
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not data.get("success"):
                raise RuntimeError(f"CWA API error: {data}")
            return data
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e):
            # Fallback for gov cert with missing Subject Key Identifier
            fallback_ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, context=fallback_ctx, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not data.get("success"):
                    raise RuntimeError(f"CWA API error: {data}")
                return data
        print(f"Failed to fetch {dataset_id}: {e}", file=sys.stderr)
        raise

def main():
    print("Testing connection with F-C0032-001 (36hr forecast)...")
    data = fetch_cwa_dataset("F-C0032-001")
    locations = [loc["locationName"] for loc in data["records"]["location"]]
    print(f"Success! Retrieved {len(locations)} locations: {', '.join(locations[:6])}...")

if __name__ == "__main__":
    main()

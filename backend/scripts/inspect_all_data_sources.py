import json
import csv
from pathlib import Path

def inspect():
    paths = [
        Path(r"d:\Schemora\data\schemes\schemes.v1.json"),
        Path(r"d:\Schemora\backend\data\final\schemes.json"),
        Path(r"d:\Schemora\backend\data\raw\scraped_schemes_raw.json"),
        Path(r"d:\Schemora\backend\data\raw\schemes_raw.json"),
        Path(r"d:\Schemora\backend\data\processed"),
    ]
    
    for p in paths:
        if p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    if isinstance(data, list):
                        print(f"{p.name}: {len(data)} items")
                    elif isinstance(data, dict):
                        items = data.get("schemes") or data.get("data") or data.get("records") or []
                        print(f"{p.name}: {len(items)} items (dict total keys: {len(data.keys())})")
                except Exception as e:
                    print(f"Error reading {p.name}: {e}")
        elif p.is_dir():
            files = list(p.glob("*.json"))
            print(f"Dir {p.name}: {len(files)} json files")

if __name__ == "__main__":
    inspect()

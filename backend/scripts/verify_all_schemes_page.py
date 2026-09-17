import asyncio
import sys
import os
import urllib.request
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import AsyncSessionLocal
from sqlalchemy import select, func
from app.models.scheme import Scheme

async def verify_schemes_catalog():
    print("==================================================")
    print(" SCHEMORA ALL SCHEMES PAGE INTEGRITY VERIFICATION ")
    print("==================================================")

    # 1. Database Count Verification
    async with AsyncSessionLocal() as db:
        res_pub = await db.execute(select(Scheme).where(Scheme.is_published == True))
        pub_schemes = res_pub.scalars().all()
        db_pub_count = len(pub_schemes)
        print(f"1. Database Published Scheme Count (`is_published == True`): {db_pub_count}")

    # 2. API Endpoint Count Verification
    url = "http://127.0.0.1:8000/api/v1/schemes?page_size=500"
    api_count = 0
    try:
        req = urllib.request.urlopen(url)
        res_body = json.loads(req.read().decode())
        if res_body.get("success"):
            data = res_body.get("data", [])
            meta = res_body.get("meta", {})
            api_count = len(data)
            total_items = meta.get("total_items")
            print(f"2. API Response Status: HTTP {req.status}")
            print(f"   API Returned Count (`len(data)`): {api_count}")
            print(f"   API Metadata `total_items`: {total_items}")
            print(f"   API Pagination Strategy: page={meta.get('page')}, page_size={meta.get('page_size')}, total_pages={meta.get('total_pages')}")
    except Exception as e:
        print(f"2. API Request Error: {e}")

    # 3. Validation Check
    print("--------------------------------------------------")
    if db_pub_count == 66 and api_count == 66:
        print("✓ SUCCESS: DB Count (66) == API Count (66) == All Schemes Catalog Count!")
    else:
        print(f"⚠ NOTICE: DB Count ({db_pub_count}), API Count ({api_count})")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(verify_schemes_catalog())

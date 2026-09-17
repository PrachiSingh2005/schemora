import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import AsyncSessionLocal
from sqlalchemy import select, func
from app.models.scheme import Scheme

async def check_count():
    async with AsyncSessionLocal() as db:
        res_published = await db.execute(select(Scheme).where(Scheme.is_published == True))
        pub_schemes = res_published.scalars().all()
        
        res_all = await db.execute(select(Scheme))
        all_schemes = res_all.scalars().all()
        
        print(f"Total schemes in DB: {len(all_schemes)}")
        print(f"Total published schemes (is_published==True): {len(pub_schemes)}")
        
        print("\n--- List of Published Schemes ---")
        for i, s in enumerate(pub_schemes, 1):
            print(f"{i}. [{s.id}] {s.title} ({s.jurisdiction} - {s.state or 'Central'})")

if __name__ == "__main__":
    asyncio.run(check_count())

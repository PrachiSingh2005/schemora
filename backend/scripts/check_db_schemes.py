import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import AsyncSessionLocal
from sqlalchemy import select, func
from app.models.scheme import Scheme
from app.models.knowledge import KnowledgeChunk

async def verify_db_counts():
    async with AsyncSessionLocal() as db:
        res_pub = await db.execute(select(Scheme).where(Scheme.is_published == True))
        pub_schemes = res_pub.scalars().all()

        res_all = await db.execute(select(Scheme))
        all_schemes = res_all.scalars().all()

        res_chunks = await db.execute(select(func.count(func.distinct(KnowledgeChunk.scheme_id))))
        chunks_schemes_count = res_chunks.scalar()

        print("==================================================")
        print(" SCHEMORA KNOWLEDGE BASE DIAGNOSTIC COUNT REPORT ")
        print("==================================================")
        print(f"Total schemes in DB (`schemes` table): {len(all_schemes)}")
        print(f"Total published schemes (`is_published == True`): {len(pub_schemes)}")
        print(f"Distinct schemes indexed in `knowledge_chunks`: {chunks_schemes_count}")
        print("--------------------------------------------------")

        for i, s in enumerate(pub_schemes, 1):
            print(f"{i:2d}. [{s.id}] {s.title} ({s.jurisdiction} - {s.state or 'Central'})")

if __name__ == "__main__":
    asyncio.run(verify_db_counts())

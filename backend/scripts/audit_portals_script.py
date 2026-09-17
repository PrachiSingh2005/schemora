import asyncio
import json
from sqlalchemy import select, or_
from app.core.database import AsyncSessionLocal
from app.models.scheme import Scheme
from app.models.knowledge import KnowledgeChunk
from app.services.query_understanding_service import get_query_understanding_service

async def audit_portals():
    print("=== 1. CANONICAL ENTITIES IN QUERY UNDERSTANDING SERVICE ===")
    qu_service = get_query_understanding_service()
    portal_keys = ["myScheme", "MahaDBT", "Aaple Sarkar DBT Portal", "NSP", "Jan Samarth"]
    
    for entity_id, entity in qu_service.entity_registry.items():
        if entity.entity_type == "PORTAL" or any(p.lower() in entity.canonical_name.lower() or p.lower() in entity.official_name.lower() or any(p.lower() in a.lower() for a in entity.aliases) for p in portal_keys):
            print(f"\n[Entity Registry] ID: {entity.id}")
            print(f"  Canonical Name: {entity.canonical_name}")
            print(f"  Official Name: {entity.official_name}")
            print(f"  Entity Type: {entity.entity_type}")
            print(f"  State: {entity.state}")
            print(f"  Description: {entity.description}")
            print(f"  Official URL: {entity.official_url}")
            print(f"  Aliases: {entity.aliases}")

    async with AsyncSessionLocal() as session:
        print("\n=== 2. SCHEME DATABASE RECORDS FOR PORTALS ===")
        stmt = select(Scheme).where(
            or_(
                Scheme.name.ilike("%myScheme%"),
                Scheme.name.ilike("%MahaDBT%"),
                Scheme.name.ilike("%Aaple Sarkar%"),
                Scheme.name.ilike("%NSP%"),
                Scheme.name.ilike("%National Scholarship Portal%"),
                Scheme.name.ilike("%Jan Samarth%"),
                Scheme.official_name.ilike("%myScheme%"),
                Scheme.official_name.ilike("%MahaDBT%"),
                Scheme.official_name.ilike("%Aaple Sarkar%"),
                Scheme.official_name.ilike("%Jan Samarth%"),
            )
        )
        res = await session.execute(stmt)
        schemes = res.scalars().all()
        print(f"Found {len(schemes)} schemes matching portal terms:")
        for s in schemes:
            print(f"\n[Scheme DB] ID: {s.id}")
            print(f"  Name: {s.name}")
            print(f"  Official Name: {s.official_name}")
            print(f"  State: {s.state}")
            print(f"  Description: {s.description[:120]}..." if s.description else "  Description: None")
            print(f"  Official Scheme URL: {s.official_scheme_url}")
            print(f"  Application URL: {s.application_url}")
            print(f"  Official Portal URL: {s.official_portal_url}")
            print(f"  Source URL: {s.source_url}")
            print(f"  Aliases: {s.aliases}")

        print("\n=== 3. KNOWLEDGE CHUNKS FOR PORTALS ===")
        stmt_chunk = select(KnowledgeChunk).where(
            or_(
                KnowledgeChunk.title.ilike("%myScheme%"),
                KnowledgeChunk.title.ilike("%MahaDBT%"),
                KnowledgeChunk.title.ilike("%Aaple Sarkar%"),
                KnowledgeChunk.title.ilike("%NSP%"),
                KnowledgeChunk.title.ilike("%Jan Samarth%"),
                KnowledgeChunk.chunk_text.ilike("%myScheme%"),
                KnowledgeChunk.chunk_text.ilike("%MahaDBT%"),
                KnowledgeChunk.chunk_text.ilike("%Aaple Sarkar%"),
                KnowledgeChunk.chunk_text.ilike("%Jan Samarth%"),
            )
        )
        res_chunk = await session.execute(stmt_chunk)
        chunks = res_chunk.scalars().all()
        print(f"Found {len(chunks)} knowledge chunks referencing portals.")
        
        # Group chunks by entity/title
        chunk_summary = {}
        for c in chunks:
            title = c.title or "Untitled"
            if title not in chunk_summary:
                chunk_summary[title] = []
            chunk_summary[title].append(c)

        for title, clist in chunk_summary.items():
            print(f"\n--- Title: {title} (Count: {len(clist)}) ---")
            c0 = clist[0]
            print(f"  Scheme ID: {c0.scheme_id}")
            print(f"  Source Type: {c0.source_type}")
            print(f"  Jurisdiction/State: {c0.jurisdiction} / {c0.state}")
            print(f"  Source URL: {c0.source_url}")
            print(f"  Snippet: {c0.chunk_text[:150]}...")

if __name__ == "__main__":
    asyncio.run(audit_portals())

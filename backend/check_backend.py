import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    print("Testing DB connection...")
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            print("DB SUCCESS:", result.scalar())
    except Exception as e:
        print("DB ERROR:", e)

if __name__ == "__main__":
    asyncio.run(main())

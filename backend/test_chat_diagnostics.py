import asyncio
import time
import sys
import logging
from pathlib import Path

# Setup logging to console
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.core.database import AsyncSessionLocal
from app.api.v1.ai import chat_assistant
from app.schemas.ai import AIChatRequest
from app.core.config import settings

async def run_diagnostics():
    print("=" * 70)
    print(" RUNNING CHAT DIAGNOSTICS FOR 'hi' AND 'farmer schemes' ")
    print(f" Configured GROQ_GENERATION_MODEL = {settings.GROQ_GENERATION_MODEL}")
    print("=" * 70)

    # 1. Test "hi"
    print("\n--- TEST 1: Question = 'hi' ---")
    t0 = time.time()
    async with AsyncSessionLocal() as session:
        req = AIChatRequest(question="hi", language="en")
        res = await chat_assistant(req, session)
        dt = round((time.time() - t0) * 1000, 2)
        print(f"Total Client Time : {dt} ms")
        print(f"Answer Snippet    : {res.data.answer[:120]}...")

    # 2. Test "farmer schemes"
    print("\n--- TEST 2: Question = 'farmer schemes' ---")
    t0 = time.time()
    async with AsyncSessionLocal() as session:
        req = AIChatRequest(question="farmer schemes", language="en")
        res = await chat_assistant(req, session)
        dt = round((time.time() - t0) * 1000, 2)
        print(f"Total Client Time : {dt} ms")
        print(f"Chunks Retrieved  : {len(res.data.retrieved_schemes)}")
        print(f"Answer Snippet    : {res.data.answer[:300]}...")

    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_diagnostics())

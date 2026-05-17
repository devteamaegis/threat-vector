import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

from agent import run_threat_agent

test_transcript = """
I'm calling because there's a student at Lincoln High School named Tyler who told
three people yesterday that he was going to bring a gun to school on Friday.
He's in 11th grade, usually wears a black hoodie. He's been making these comments
for the past two weeks and people are scared.
"""

async def main():
    print("=== Threat Vector Pipeline Test ===\n")
    result = await run_threat_agent("test-001", test_transcript)
    print("\n=== Classification Result ===")
    print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())

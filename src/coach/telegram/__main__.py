import asyncio
import logging

from dotenv import load_dotenv

from coach.telegram.bot import CoachBot

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    asyncio.run(CoachBot().run())

import asyncio

from dotenv import load_dotenv

from coach.telegram.bot import CoachBot

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(CoachBot().run())

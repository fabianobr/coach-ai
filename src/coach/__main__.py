from dotenv import load_dotenv

from coach.cli import CoachCLI

if __name__ == "__main__":
    load_dotenv()
    cli = CoachCLI()
    cli.run()

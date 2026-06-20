"""Run the voice-agent server.

    python main.py
or
    uvicorn app:app --host 0.0.0.0 --port 8080
"""

from dotenv import load_dotenv

load_dotenv()

import uvicorn

import config

if __name__ == "__main__":
    uvicorn.run("app:app", host=config.HOST, port=config.PORT)

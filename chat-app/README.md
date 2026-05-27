# CURIOSS Pattern Explorer — Chat App

A FastAPI + Claude-powered chat interface for exploring the CURIOSS patterns collection.

## Prerequisites

- Python 3.9+
- An [Anthropic API key](https://console.anthropic.com/)

## Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Copy the example env file and add your API key:

   ```bash
   cp .env.example .env
   ```

   Then edit `.env` and replace `your_api_key_here` with your actual key.

## Running

From the `chat-app/` directory:

```bash
./start.sh
```

Or directly with uvicorn:

```bash
python3 -m uvicorn app:app --port 8765 --reload
```

Then open [http://localhost:8765](http://localhost:8765) in your browser.

## How it works

- The app loads all `.md` pattern files from the parent directory at startup and builds a system prompt from them.
- `/api/chat` streams responses from `claude-sonnet-4-6` using the full patterns collection as context.
- `/api/patterns` returns a list of all patterns with titles, summaries, and tags.
- `/api/pattern/{id}` returns the full content of a single pattern.

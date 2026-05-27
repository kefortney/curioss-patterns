import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import anthropic
import yaml
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()
client = anthropic.Anthropic()

PATTERNS_DIR = Path(__file__).parent.parent
SKIP_FILES = {"README.md", "CONTRIBUTING.md", "PATTERN-TEMPLATE.md"}


def parse_frontmatter(content: str):
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return {}, content
    try:
        frontmatter = yaml.safe_load(match.group(1)) or {}
    except Exception:
        frontmatter = {}
    return frontmatter, content[match.end() :]


def load_patterns():
    patterns = []
    for filepath in sorted(PATTERNS_DIR.glob("*.md")):
        if filepath.name in SKIP_FILES:
            continue
        try:
            content = filepath.read_text(encoding="utf-8")
        except Exception:
            continue

        frontmatter, body = parse_frontmatter(content)

        title_match = re.search(r"^# (.+)$", body, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else filepath.stem

        # Extract first real sentence from Pattern Summary section
        summary = ""
        summary_match = re.search(
            r"## Pattern Summary\s*\n(.*?)(?=\n## |\Z)", body, re.DOTALL
        )
        if summary_match:
            raw = summary_match.group(1).strip()
            # Strip italicized template instructions
            raw = re.sub(r"^\*[^*]+\*\s*\n\s*\n?", "", raw).strip()
            # Take first non-empty line
            for line in raw.split("\n"):
                line = line.strip().lstrip("*").rstrip("*").strip()
                if line and len(line) > 15:
                    summary = line
                    break

        tags = frontmatter.get("tags", [])
        if not isinstance(tags, list):
            tags = []

        patterns.append(
            {
                "id": filepath.stem,
                "title": title,
                "summary": summary[:250],
                "tags": [t.strip() for t in tags],
                "content": body,
            }
        )
    return patterns


PATTERNS = load_patterns()


def build_system_prompt():
    lines = [
        f"You are a knowledgeable and friendly advisor helping university staff, faculty, "
        f"and administrators explore the CURIOSS patterns collection — {len(PATTERNS)} proven "
        f"patterns developed by Open Source Program Offices (OSPOs) at universities and "
        f"research institutions worldwide.\n\n"
        "Your role: help users understand which patterns apply to their situation, how to "
        "implement them, and how patterns can be combined for complex challenges.\n\n"
        "Guidelines:\n"
        "- **Bold the exact pattern title** when recommending it (e.g. **Summer Internship Program**)\n"
        "- Explain concretely why each pattern fits the user's context\n"
        "- Reference specific universities from Known Instances sections when helpful\n"
        "- Suggest combinations of related patterns for complex problems\n"
        "- Be practical about resource and staffing constraints common in academic OSPOs\n"
        "- For users just starting an OSPO, guide them toward foundational patterns first\n\n"
        "FULL PATTERNS COLLECTION:\n\n",
    ]

    for p in PATTERNS:
        tags_str = ", ".join(p["tags"]) if p["tags"] else "General"
        lines.append(
            f"=== {p['title']} ===\n"
            f"ID: {p['id']}\n"
            f"Tags: {tags_str}\n\n"
            f"{p['content']}\n\n"
        )

    prompt = "".join(lines)
    print(
        f"Loaded {len(PATTERNS)} patterns. System prompt: {len(prompt):,} chars",
        file=sys.stderr,
    )
    return prompt


SYSTEM_PROMPT = build_system_prompt()


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


@app.get("/api/patterns")
def get_patterns():
    return [
        {"id": p["id"], "title": p["title"], "summary": p["summary"], "tags": p["tags"]}
        for p in PATTERNS
    ]


@app.get("/api/pattern/{pattern_id}")
def get_pattern(pattern_id: str):
    for p in PATTERNS:
        if p["id"] == pattern_id:
            return {"id": p["id"], "title": p["title"], "tags": p["tags"], "content": p["content"]}
    return {"error": "not found"}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    async def generate():
        try:
            with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[
                    {"role": m.role, "content": m.content} for m in request.messages
                ],
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'text': text})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


app.mount("/", StaticFiles(directory="static", html=True), name="static")

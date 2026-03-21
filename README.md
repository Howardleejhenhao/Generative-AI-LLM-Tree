# LLM-Tree

LLM-Tree is a Django-based experimental chat workspace that treats conversations as a branchable DAG-style canvas instead of a linear thread.

## Current Features

- Django 5 project with Docker Compose startup and environment-variable based settings
- Graph-first workspace UI built with Django Templates plus modular JavaScript
- Workspace switching and workspace creation
- Conversation nodes with parent-child branching, edited variants, and persisted canvas positions
- Node-focused chat view with lineage, child branch navigation, and versioning context
- OpenAI and Gemini provider abstraction with per-node model selection
- Branch-local context construction based only on the selected lineage path
- Streaming assistant replies over SSE from the backend to the browser
- Graph ergonomics including drag-to-reposition, pan, zoom, fit view, minimap, search, shortcuts, and collapsible inspector

## Run With Docker Compose

1. Create `.env` from `.env.example`.
2. Build and start the app:

```bash
docker compose up --build
```

3. Open `http://127.0.0.1:8000`.

## Local Python Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Environment

- `OPENAI_API_KEY` and `GEMINI_API_KEY` must be set in `.env` for live model calls.
- Without provider keys, the app falls back to a clearly labeled placeholder response so the graph flow remains demoable.

## Current Workflow

1. Open a workspace graph.
2. Create a root conversation node or branch from an existing node.
3. Open a node chat view to continue that branch with streaming replies.
4. Edit an existing node into a version-safe variant when you want to fork from revised history.
5. Reposition, search, zoom, and inspect the graph as the workspace grows.

## Next Milestones

- Tighten production readiness around provider error handling and cross-provider streaming behavior
- Continue refining versioning and branch comparison UX
- Keep polishing the full-page graph workspace for demo flow and readability

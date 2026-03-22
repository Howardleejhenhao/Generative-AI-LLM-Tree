# LLM-Tree

LLM-Tree is a Django-based experimental chat workspace that treats conversations as a branchable graph instead of a single linear thread. The main interface is a graph-first canvas where each node represents a conversation unit, and every continuation can branch from any earlier point in the history.

The project is intentionally built with Django Templates plus modular JavaScript rather than a separate SPA. It runs through Docker Compose, stores secrets in `.env`, supports both OpenAI and Gemini, streams replies into the UI, and keeps generation context branch-local.

## What The App Does

- Renders a full-page graph workspace for conversation trees
- Lets you create multiple workspaces and switch between them
- Stores conversation nodes with ordered message lists instead of forcing a single prompt/response pair
- Supports branching from any existing node
- Supports version-safe edited variants of older nodes
- Lets each new node choose its provider and model independently
- Streams assistant replies to the browser over SSE
- Preserves branch-local context by building prompts only from the selected lineage
- Persists manual node positions so graph layouts remain stable
- Provides a dedicated chat page for each node in addition to the graph view

## Current Feature Summary

### Graph Workspace

- Graph canvas rendered from Django payloads with modular frontend JavaScript
- Node selection and inspector panel
- Root node creation and child node creation from any selected node
- Workspace creation and deletion
- Search, zoom, fit view, minimap, pan, and keyboard shortcuts
- Drag-to-reposition nodes with persisted `x/y` coordinates
- Node subtree deletion

### Node-Focused Chat

- Dedicated page for a selected node
- Ordered transcript rendering from that node's internal messages
- Composer for continuing the branch
- Automatic in-place continuation for leaf nodes
- Automatic child-branch creation when replying from a historical node that already has children
- Lineage navigation and child branch links
- Edited-source and edited-variant navigation

### Providers And Generation

- OpenAI and Gemini provider abstraction behind shared service interfaces
- Per-node provider and model selection
- Backend SSE streaming from upstream provider streams
- Legacy Gemini model alias resolution for older saved nodes
- Clearly labeled fallback responses when provider keys are missing or upstream streaming fails before any tokens arrive

## Core Concepts

### Workspace

A workspace is one conversation canvas. It owns a set of conversation nodes and is the top-level unit shown in the main graph UI.

### Conversation Node

A conversation node is a graph node. It stores:

- a parent reference for branching
- an optional `edited_from` reference for version-safe edited variants
- provider and model metadata
- persisted graph position
- a short title and summary
- an ordered list of messages

### Node Message

Each node contains one or more ordered messages with roles such as `system`, `user`, or `assistant`. This lets a node represent either a single exchange or a short bundled sequence.

### Branch-Local Memory

When LLM-Tree generates a new reply, it walks only the current lineage:

`root -> ... -> selected node -> new prompt`

Sibling branches are excluded from the prompt context on purpose.

### Edited Variants

Editing old history does not overwrite the original node. Instead, the app creates a new variant node linked through `edited_from`, so the original branch remains intact.

## Architecture

### Stack

- Backend: Django 5
- Frontend: Django Templates + modular vanilla JavaScript
- Database: SQLite by default
- Container runtime: Docker Compose
- Providers: OpenAI Responses API and Gemini Generate Content / Stream Generate Content

### Repository Layout

```text
.
|-- llm_tree_project/          # Django project settings and root URLs
|-- tree_ui/
|   |-- models.py             # Workspace, ConversationNode, NodeMessage
|   |-- views.py              # Graph page, node chat page, JSON/SSE endpoints
|   |-- services/             # Context building, node creation/editing, providers
|   |-- templates/tree_ui/    # Django templates
|   `-- static/tree_ui/js/    # Canvas, viewport, API, streaming, chat behavior
|-- docker-compose.yml
|-- Dockerfile
|-- entrypoint.sh             # Runs migrations before starting Django
|-- .env.example
`-- docs/agent-progress.md    # Ongoing development log
```

### Backend Service Boundaries

- `tree_ui/services/context_builder.py`: lineage-only prompt construction
- `tree_ui/services/node_creation.py`: node creation, continuation, reply streaming, fallback behavior
- `tree_ui/services/node_editing.py`: edited variant creation
- `tree_ui/services/model_catalog.py`: provider defaults and legacy Gemini alias mapping
- `tree_ui/services/providers/`: provider-specific OpenAI and Gemini integrations behind a shared interface

## Running The Project

### Option 1: Docker Compose

This is the default development path for the project.

1. Copy the environment file.

```bash
cp .env.example .env
```

2. Fill in any values you want to change. Add `OPENAI_API_KEY` and/or `GEMINI_API_KEY` if you want live model calls.

3. Build and start the app.

```bash
docker compose up --build
```

4. Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

Notes:

- The container entrypoint automatically runs `python manage.py migrate --noinput`.
- Source code is mounted into the container with `.:/app` for live development.
- The default command is `python manage.py runserver 0.0.0.0:8000`.

### Option 2: Local Python Environment

If you want to run without Docker:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

The project also notes that a `pyenv` environment may be available:

```bash
pyenv activate LLM-Tree
```

That is optional. Docker Compose remains the default expected runtime path.

## Environment Variables

The app reads configuration from `.env`. Do not commit secrets.

| Variable | Purpose | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django secret key | `django-dev-key-change-me` fallback in settings |
| `DJANGO_DEBUG` | Enables debug mode | `true` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts | `127.0.0.1,localhost` |
| `DJANGO_TIME_ZONE` | Django timezone | `Asia/Taipei` |
| `DJANGO_SQLITE_PATH` | SQLite database path relative to project root | `db.sqlite3` |
| `LLM_REQUEST_TIMEOUT_SECONDS` | Provider request timeout | `30` |
| `LLM_STREAM_CHUNK_DELAY_SECONDS` | Artificial delay used only for fallback chunk streaming | `0.02` |
| `OPENAI_API_KEY` | OpenAI API key | empty |
| `GEMINI_API_KEY` | Gemini API key | empty |

## Default Model Choices

Current defaults in code:

- OpenAI: `gpt-4.1-mini`
- Gemini: `gemini-2.5-flash`

Legacy Gemini names such as `gemini-2.0-flash` are transparently mapped to current supported models when old nodes are loaded or executed.

## Typical Workflow

1. Open the app and land in the current workspace graph.
2. Create a workspace if you want a separate conversation canvas.
3. Create a root node and choose a provider/model.
4. Open the node's chat page and send a prompt.
5. Watch the assistant reply stream into the UI.
6. Return to the graph and branch from any existing node.
7. Drag nodes to rearrange the canvas and keep the layout.
8. If you want to revise history, create an edited variant rather than overwriting the original node.

## HTTP Surface

Main routes:

- `/` redirects to the current or default workspace
- `/workspaces/<slug>/` renders the graph workspace
- `/workspaces/<slug>/nodes/<node_id>/` renders the node-focused chat page

Key API routes:

- `POST /api/workspaces/`
- `POST /api/workspaces/<slug>/delete/`
- `POST /api/workspaces/<slug>/nodes/`
- `POST /api/workspaces/<slug>/nodes/<node_id>/delete/`
- `POST /api/workspaces/<slug>/nodes/<node_id>/position/`
- `POST /api/workspaces/<slug>/nodes/stream/`
- `POST /api/workspaces/<slug>/nodes/<node_id>/messages/stream/`
- `POST /api/workspaces/<slug>/nodes/<node_id>/edit-variant/`

## Development Checks

Useful validation commands:

```bash
python manage.py check
python manage.py test
node --check tree_ui/static/tree_ui/js/app.js
node --check tree_ui/static/tree_ui/js/node-chat.js
node --check tree_ui/static/tree_ui/js/model-options.js
```

## Notes On Provider Behavior

- With valid API keys, OpenAI and Gemini responses stream from the upstream provider into the browser-facing SSE endpoints.
- If no key is configured, or a provider fails before any streamed text is emitted, the app returns a clearly labeled fallback response so the branching workflow remains demoable.
- If a provider fails after streaming has already started, the error is treated as a real streaming failure rather than being silently replaced.

## Known Limits

- The data model is still a single-parent branching tree even though the UI is graph-like.
- SQLite is the default development database; no production database configuration is included yet.
- Provider integrations are implemented directly with HTTP requests and currently focus on text generation workflows.
- Browser verification against live provider keys is still the main remaining hardening step for streaming edge cases.

## Progress Tracking

Ongoing implementation history is recorded in [docs/agent-progress.md](docs/agent-progress.md). That file is the persistent development log across sessions and includes branch, commit, push, and next-step notes.

# LLM-Tree

LLM-Tree is a Django-based experimental chat workspace that treats conversations as a branchable DAG-style canvas instead of a linear thread.

## Current Bootstrap Scope

- Django 5 project and initial `tree_ui` app
- Graph-oriented data models for workspaces, nodes, and message bundles
- Django Template homepage with modular JavaScript canvas rendering
- Docker Compose based development startup
- Environment-variable driven settings for secrets and runtime config

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

## Next Milestones

- Real provider calls for OpenAI and Gemini with streaming
- Streaming response generation
- Node editing and re-branch creation flow

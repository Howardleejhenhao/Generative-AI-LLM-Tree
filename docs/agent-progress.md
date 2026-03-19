# Agent Progress Log

## Ongoing Development Notes
- Frontend architecture must stay as **Django Templates + JavaScript**, not SPA
- Streaming is mandatory
- Model providers must include **OpenAI** and **Gemini**
- Secrets must only live in `.env`
- Docker Compose startup is mandatory
- Branch-local context is mandatory
- Editing old node and re-branching is mandatory
- Branch / commit / push discipline must be strict and documented every session
- A pyenv environment may be used with `pyenv activate LLM-Tree`, but Docker Compose remains the default runtime path

## Session 2026-03-19 16:50

### Session Goal
- Bootstrap the repository into a runnable Django + Docker Compose MVP foundation.
- Establish the persistent progress log and initial project structure.

### Planned Tasks
- inspect repository state and current git branch
- create the dedicated progress log file
- scaffold the Django project and initial app structure
- add Docker Compose based startup and environment configuration
- verify the generated project locally where possible

### Work Completed
- Inspected repository state, current branch, available tooling, and confirmed the project was still unbootstrapped.
- Created the dedicated agent progress log required by the workflow.
- Scaffolded the Django project and the initial `tree_ui` app.
- Added graph-oriented data models for `Workspace`, `ConversationNode`, and `NodeMessage`.
- Built the first Django Template based landing page with a DAG-style canvas shell and a detail panel.
- Split frontend behavior into separate static JavaScript modules for canvas rendering, node detail rendering, API helpers, and streaming status messaging.
- Added Docker Compose based startup with `Dockerfile`, `docker-compose.yml`, `.env.example`, and an entrypoint that runs migrations before starting Django.
- Verified the project with `python3 manage.py check`, `python3 manage.py makemigrations tree_ui`, `python3 manage.py test`, and `python3 manage.py migrate --noinput`.
- Committed and pushed the bootstrap slice.

### Files Changed
- `README.md`
- `.env.example`
- `Dockerfile`
- `docker-compose.yml`
- `entrypoint.sh`
- `docs/agent-progress.md`
- `llm_tree_project/settings.py`
- `llm_tree_project/urls.py`
- `manage.py`
- `requirements.txt`
- `tree_ui/admin.py`
- `tree_ui/models.py`
- `tree_ui/tests.py`
- `tree_ui/urls.py`
- `tree_ui/views.py`
- `tree_ui/migrations/0001_initial.py`
- `tree_ui/services/demo_graph.py`
- `tree_ui/templates/tree_ui/base.html`
- `tree_ui/templates/tree_ui/index.html`
- `tree_ui/static/tree_ui/css/app.css`
- `tree_ui/static/tree_ui/js/api.js`
- `tree_ui/static/tree_ui/js/app.js`
- `tree_ui/static/tree_ui/js/canvas.js`
- `tree_ui/static/tree_ui/js/node-panel.js`
- `tree_ui/static/tree_ui/js/streaming.js`

### Git Workflow
- Current branch at session start: `feature/bootstrap-django-docker`
- New branch created/switched: `feature/bootstrap-django-docker`
- Commits made:
  - `1ac1ff3` - `feat: bootstrap django graph workspace`
- Push status:
  - pushed to `origin/feature/bootstrap-django-docker`

### Current Status
- The repository now has a runnable Django + Docker Compose foundation.
- The main page renders a graph-style conversation workspace shell using Django Templates and modular JavaScript.
- Core graph data models exist and initial migrations are committed.

### Next Recommended Step
- Implement the first real node creation flow and persist graph data to the database from the UI.
- Add provider abstraction layers for OpenAI and Gemini so new nodes can choose a model per branch.
- Begin the streaming response path after node creation is wired.

### Known Issues / Blockers / Tech Debt
- The UI currently renders demo graph data when the database has no workspace records.
- Provider integration, branch-local context assembly, live streaming, and edit/re-branch behavior are not implemented yet.
- `AGENTS.md` remains untracked in the worktree and was intentionally not included in the bootstrap commit.

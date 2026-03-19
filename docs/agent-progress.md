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

## Session 2026-03-19 17:03

### Session Goal
- Replace the demo-only graph with a database-backed workspace flow.
- Let the UI create and persist root nodes and child branches from the page.

### Planned Tasks
- inspect the current implementation and preserve any existing uncommitted changes
- add backend services and API endpoints for default workspace loading and node creation
- update the template and JavaScript so users can create nodes from the UI
- verify the flow with tests and local Django checks

### Work Completed
- Session started; current branch, worktree state, and latest progress log were reviewed.
- Existing `entrypoint.sh` worktree change was inspected before implementation.
- Replaced the demo-only homepage flow with a default workspace loaded from the database.
- Added backend services to serialize graph payloads, provision the default workspace, and create nodes with stubbed assistant replies.
- Added a POST API endpoint for creating root nodes and child branches in the selected workspace.
- Updated the Django Template and modular JavaScript so the UI can create nodes, choose provider/model, and refresh the graph without reloading.
- Added test coverage for homepage workspace provisioning plus root and child node creation.
- Verified the implementation with `python3 manage.py check` and `python3 manage.py test`.

### Files Changed
- `docs/agent-progress.md`
- `entrypoint.sh`
- `tree_ui/static/tree_ui/css/app.css`
- `tree_ui/static/tree_ui/js/api.js`
- `tree_ui/static/tree_ui/js/app.js`
- `tree_ui/static/tree_ui/js/canvas.js`
- `tree_ui/templates/tree_ui/index.html`
- `tree_ui/tests.py`
- `tree_ui/urls.py`
- `tree_ui/views.py`
- `tree_ui/services/graph_payload.py`
- `tree_ui/services/node_creation.py`
- `tree_ui/services/workspace_service.py`

### Git Workflow
- Current branch at session start: `feature/bootstrap-django-docker`
- New branch created/switched: `feature/node-creation-flow`
- Commits made:
  - `25ddeda` - `feat: add workspace-backed node creation flow`
- Push status:
  - not pushed yet in this session

### Current Status
- The page now uses a real default workspace instead of the temporary demo payload.
- Users can create a root node or branch from a selected node directly from the side panel.
- New nodes are persisted in SQLite and rendered immediately on the graph.

### Next Recommended Step
- Replace the stubbed assistant reply generator with real OpenAI and Gemini provider abstractions.
- Add branch-local context assembly for provider requests and prepare the streaming transport.

### Known Issues / Blockers / Tech Debt
- Assistant replies are still stubbed locally; real provider calls and streaming are not wired yet.
- Node editing and version-safe re-branching remain unimplemented.

## Session 2026-03-19 17:13

### Session Goal
- Introduce provider abstraction and branch-local context building behind the node creation flow.
- Keep the app runnable even when provider API keys are not configured.

### Planned Tasks
- inspect the current node creation implementation and provider-related settings gaps
- add branch-local context builder and provider abstraction modules
- update node creation to use provider services with safe fallback behavior
- verify the new behavior with tests and local Django checks

### Work Completed
- Session started; repository state, active branch, and progress log were reviewed.
- Planned the next slice around provider abstraction and lineage-scoped context assembly.
- Added environment-driven provider settings for OpenAI, Gemini, and request timeout handling.
- Added a branch-local context builder that assembles only the selected lineage plus the new prompt.
- Introduced provider abstraction modules for OpenAI and Gemini behind a registry-based service interface.
- Updated node creation to call the provider layer and fall back safely when API keys are missing or requests fail.
- Updated the UI copy to reflect provider-backed generation with safe fallback behavior.
- Added tests for lineage-scoped context assembly and provider-result usage inside node creation.
- Verified the implementation with `python3 manage.py check` and `python3 manage.py test`.

### Files Changed
- `docs/agent-progress.md`
- `.env.example`
- `README.md`
- `llm_tree_project/settings.py`
- `tree_ui/services/context_builder.py`
- `tree_ui/services/node_creation.py`
- `tree_ui/services/providers/__init__.py`
- `tree_ui/services/providers/base.py`
- `tree_ui/services/providers/gemini_provider.py`
- `tree_ui/services/providers/openai_provider.py`
- `tree_ui/services/providers/registry.py`
- `tree_ui/templates/tree_ui/index.html`
- `tree_ui/tests.py`

### Git Workflow
- Current branch at session start: `feature/node-creation-flow`
- New branch created/switched: `feature/provider-context-abstraction`
- Commits made:
  - none yet in this session
- Push status:
  - not pushed yet in this session

### Current Status
- Node creation now builds a lineage-scoped message context before generation.
- OpenAI and Gemini generation are routed through separate service modules with a shared interface.
- The app still works without API keys because generation falls back to a local explanatory assistant message.

### Next Recommended Step
- Add a streaming transport layer on top of the provider abstraction so partial tokens can reach the UI.
- Persist provider metadata or generation status on nodes if streaming state needs to survive refreshes.

### Known Issues / Blockers / Tech Debt
- `AGENTS.md` is still untracked and should remain outside the feature commits unless explicitly requested.
- Provider calls are currently synchronous and non-streaming.
- OpenAI and Gemini integrations are intentionally wrapped with fallback behavior, so missing keys do not hard-fail the UI.

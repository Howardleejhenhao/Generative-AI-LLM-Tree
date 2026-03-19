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
  - `caa95a6` - `feat: add provider abstraction and branch context`
  - `254fa7c` - `docs: update agent progress log`
- Push status:
  - pushed to `origin/feature/provider-context-abstraction`

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

## Session 2026-03-19 18:36

### Session Goal
- Fix the graph viewport so users can drag the canvas to inspect off-screen nodes.
- Preserve existing node selection and creation behavior while adding panning.

### Planned Tasks
- inspect the current canvas DOM/CSS/JS layout and identify the cleanest pan architecture
- add a draggable graph viewport with horizontal and vertical movement
- keep node click selection working after the pan behavior is added
- verify the change locally and update the progress log

### Work Completed
- Session started; repository state, active branch, and progress log were reviewed.
- Confirmed the current issue: graph content can extend past the visible area with no way to pan.
- Reworked the graph stage into a fixed viewport plus a movable canvas surface.
- Added drag-to-pan behavior so the workspace can be moved horizontally and vertically with the mouse.
- Kept node selection intact while preventing accidental clicks during drag gestures.
- Added a small on-canvas hint so the drag interaction is discoverable.
- Added a minimal homepage assertion for the new pan hint text.
- Verified the change with `python3 manage.py check` and `python3 manage.py test`.

### Files Changed
- `docs/agent-progress.md`
- `tree_ui/static/tree_ui/css/app.css`
- `tree_ui/static/tree_ui/js/app.js`
- `tree_ui/static/tree_ui/js/canvas.js`
- `tree_ui/static/tree_ui/js/viewport.js`
- `tree_ui/templates/tree_ui/index.html`
- `tree_ui/tests.py`

### Git Workflow
- Current branch at session start: `feature/provider-context-abstraction`
- New branch created/switched: `feature/canvas-pan-drag`
- Commits made:
  - `385987e` - `feat: add drag-to-pan graph viewport`
  - `746ecec` - `docs: update agent progress log`
- Push status:
  - pushed to `origin/feature/canvas-pan-drag`

### Current Status
- The graph viewport now supports drag-to-pan in all directions when nodes exist.
- Existing node selection and branch creation behavior remain intact.

### Next Recommended Step
- Add streaming transport on top of the existing provider abstraction.
- Consider adding zoom controls or a mini-map after streaming if the graph grows large.

### Known Issues / Blockers / Tech Debt
- `AGENTS.md` remains untracked and outside feature commits.
- The current graph viewport supports panning but not zooming yet.

## Session 2026-03-19 18:45

### Session Goal
- Fix the graph empty-state so it disappears as soon as real nodes exist.
- Preserve the new drag-to-pan viewport behavior.

### Planned Tasks
- inspect the empty-state rendering path across template, CSS, and canvas JS
- ensure hidden state is respected on initial render and subsequent client updates
- verify the fix with local Django checks and tests

### Work Completed
- Session started; current branch and worktree state were reviewed.
- Fixed the graph empty-state to hide correctly when workspace nodes already exist.
- Added server-rendered `hidden` protection plus CSS handling for `.graph-empty[hidden]`.
- Switched the client-side empty-state toggle to attribute-based control for consistency.
- Verified the fix with `python3 manage.py check` and `python3 manage.py test`.

### Files Changed
- `docs/agent-progress.md`
- `tree_ui/static/tree_ui/css/app.css`
- `tree_ui/static/tree_ui/js/canvas.js`
- `tree_ui/templates/tree_ui/index.html`

### Git Workflow
- Current branch at session start: `feature/canvas-pan-drag`
- New branch created/switched: `feature/canvas-pan-drag`
- Commits made:
  - `938a7e3` - `fix: hide graph empty state when nodes exist`
- Push status:
  - pushed to `origin/feature/canvas-pan-drag`

### Current Status
- The empty-state banner no longer persists over real graph content.

### Next Recommended Step
- Add streaming transport for node generation on top of the current provider abstraction.

### Known Issues / Blockers / Tech Debt
- `AGENTS.md` remains untracked and outside feature commits.

## Session 2026-03-19 18:48

### Session Goal
- Add streaming transport for node generation on top of the current provider abstraction.
- Keep the app usable without billing or configured API keys by streaming fallback output.

### Planned Tasks
- inspect the current synchronous node creation path and identify streaming integration points
- add a streaming backend endpoint for incremental node generation
- update the front-end to read streamed events and show live assistant output in the detail panel
- verify the streaming path with local Django checks and tests

### Work Completed
- Session started; current branch, recent commits, and repository state were reviewed.
- Created a new feature branch for streaming node generation.
- Added environment settings for stream chunk timing.
- Refactored node creation so validated inputs can be reused by both synchronous creation and streaming creation.
- Added a streaming node-generation endpoint using `StreamingHttpResponse` and SSE-style events.
- Added front-end stream parsing and a live preview state in the detail panel for preview, delta, node, and error events.
- Kept the existing synchronous creation endpoint available while switching the UI to the new streaming endpoint.
- Added streaming API test coverage and verified the implementation with `python3 manage.py check` and `python3 manage.py test`.

### Files Changed
- `docs/agent-progress.md`
- `.env.example`
- `llm_tree_project/settings.py`
- `tree_ui/services/node_creation.py`
- `tree_ui/static/tree_ui/js/app.js`
- `tree_ui/static/tree_ui/js/node-panel.js`
- `tree_ui/static/tree_ui/js/streaming.js`
- `tree_ui/templates/tree_ui/index.html`
- `tree_ui/tests.py`
- `tree_ui/urls.py`
- `tree_ui/views.py`

### Git Workflow
- Current branch at session start: `feature/canvas-pan-drag`
- New branch created/switched: `feature/streaming-node-generation`
- Commits made:
  - `d7201a9` - `feat: stream node generation to the UI`
  - `1beb4ce` - `docs: update agent progress log`
- Push status:
  - pushed to `origin/feature/streaming-node-generation`

### Current Status
- New node generation now streams preview text into the UI before the node is committed to the graph.
- The fallback path also streams incrementally, so the interaction can be tested without active billing.

### Next Recommended Step
- Replace local chunked provider output with true upstream streaming from OpenAI and Gemini when keys are available.
- Add cancellation and streaming status persistence if interrupted generations need to survive refreshes.

### Known Issues / Blockers / Tech Debt
- `AGENTS.md` remains untracked and outside feature commits.
- Current provider calls still fetch the full reply before chunking it locally; upstream provider-native streaming is the next refinement.

## Session 2026-03-19 18:56

### Session Goal
- Allow multiple root conversations to be created inside the same workspace.
- Remove the UI limitation that forces every new node under the currently selected node.

### Planned Tasks
- inspect the current node creation form state and confirm the root-node limitation is frontend-only
- add an explicit root-conversation creation mode in the form
- verify the backend already supports repeated root creation and add a regression test
- update the progress log with the completed behavior and next recommended step

### Work Completed
- Session started; current branch, worktree state, and progress log were reviewed.
- Confirmed the current limitation comes from the front-end always submitting the selected node as parent.
- Added an explicit root-conversation toggle to the node creation form.
- Updated the form state and submit logic so a selected node no longer blocks creating a separate top-level conversation.
- Adjusted composer copy so the UI reflects that the panel can create both child branches and new root conversations.
- Added a regression test proving the same workspace can persist multiple root nodes.
- Verified the change with `python3 manage.py check` and `python3 manage.py test`.

### Files Changed
- `docs/agent-progress.md`
- `tree_ui/static/tree_ui/css/app.css`
- `tree_ui/static/tree_ui/js/app.js`
- `tree_ui/templates/tree_ui/index.html`
- `tree_ui/tests.py`

### Git Workflow
- Current branch at session start: `feature/streaming-node-generation`
- New branch created/switched: `feature/multi-root-node-creation`
- Commits made:
  - `57fb2d6` - `feat: allow multiple root conversations per workspace`
  - `680e913` - `docs: update agent progress log`
- Push status:
  - pushed to `origin/feature/multi-root-node-creation`

### Current Status
- The same workspace can now contain multiple root conversations, each representing a separate top-level dialog.
- Child branching still works from the selected node when root mode is off.

### Next Recommended Step
- Add edit-and-rebranch support so older nodes can fork revised conversation paths without destructive overwrite.
- Consider workspace-level filters or grouping if the number of root conversations grows large.

### Known Issues / Blockers / Tech Debt
- `AGENTS.md` remains untracked and outside feature commits.

## Session 2026-03-19 19:05

### Session Goal
- Update `AGENTS.md` so future sessions explicitly treat three additional product requirements as planned work.
- Record the new roadmap direction in persistent progress notes.

### Planned Tasks
- inspect the current instruction file and place the new requirements in the most relevant product and UX sections
- add the requested future requirements for node-focused chat view, draggable nodes, and zoomable full-page graph
- update the progress log so the next session sees the newly recorded direction immediately

### Work Completed
- Session started; current branch, repository state, `AGENTS.md`, and the progress log were reviewed.
- Updated `AGENTS.md` to explicitly record:
  - node-focused conversation view for each selected node
  - manual mouse-driven node repositioning
  - zoomable graph workspace that can occupy the main page experience
- Added these expectations to the product requirements, frontend approach, UX ideas, MVP priority order, and definition of done sections.
- Recorded the roadmap update in the persistent progress log.

### Files Changed
- `AGENTS.md`
- `docs/agent-progress.md`

### Git Workflow
- Current branch at session start: `feature/multi-root-node-creation`
- New branch created/switched: `feature/multi-root-node-creation`
- Commits made:
  - `21ce806` - `docs: update agent roadmap requirements`
  - `1f79d1e` - `docs: finalize agent progress log`
- Push status:
  - pushed to `origin/feature/multi-root-node-creation`

### Current Status
- The instruction file now explicitly captures the newly requested future features.

### Next Recommended Step
- Resume feature implementation from the updated roadmap, likely starting with edit-and-rebranch or multi-workspace support depending on product priority.

### Known Issues / Blockers / Tech Debt
- `AGENTS.md` was previously untracked; it should now be tracked because the user explicitly requested updates to it.

## Session 2026-03-19 19:09

### Session Goal
- Implement version-safe editing of an old node and allow re-branching from the edited result.
- Preserve original history while making the edited variant selectable like any other node.

### Planned Tasks
- inspect the current data model and graph payload for edit metadata support
- add backend services and API endpoints for creating edited node variants
- update the detail panel UI so a selected node can be edited into a new version
- verify the edit-and-rebranch flow with tests and local Django checks

### Work Completed
- Session started; current branch, repository state, `AGENTS.md`, and progress log were reviewed.
- Confirmed that the model already includes `edited_from`, so the next step is wiring the workflow and UI.
- Added a backend service for creating version-safe edited node variants without overwriting the original node.
- Added an API endpoint for turning a selected node into an edited variant.
- Updated the detail panel so a selected node can be edited into a new version from the UI.
- Preserved original message bundles while letting the edited variant be selected and branched like any other node.
- Replaced a few user-content rendering paths with safer DOM creation instead of string-based HTML injection.
- Added regression tests for edited variant creation through both the service layer and API.
- Verified the implementation with `python3 manage.py check` and `python3 manage.py test`.

### Files Changed
- `docs/agent-progress.md`
- `tree_ui/services/node_editing.py`
- `tree_ui/static/tree_ui/css/app.css`
- `tree_ui/static/tree_ui/js/app.js`
- `tree_ui/static/tree_ui/js/canvas.js`
- `tree_ui/static/tree_ui/js/node-panel.js`
- `tree_ui/templates/tree_ui/index.html`
- `tree_ui/tests.py`
- `tree_ui/urls.py`
- `tree_ui/views.py`

### Git Workflow
- Current branch at session start: `feature/multi-root-node-creation`
- New branch created/switched: `feature/edit-node-rebranch`
- Commits made:
  - `9a18243` - `feat: allow editing node into a new branchable variant`
  - `5ae88b7` - `docs: update agent progress log`
- Push status:
  - pushed to `origin/feature/edit-node-rebranch`

### Current Status
- Users can now create an edited node variant from a selected historical node without mutating the original.
- The edited variant is persisted, selectable on the graph, and can be used as the base for future branches.

### Next Recommended Step
- Add multi-workspace support so separate graphs can be created and switched explicitly.
- Consider evolving the edited variant UI into the future node-focused chat view described in `AGENTS.md`.

### Known Issues / Blockers / Tech Debt
- `AGENTS.md` is now tracked and should stay aligned with implementation decisions.
- The current edit UI works on the node detail panel; the dedicated node-focused chat view is still future work.

## Session 2026-03-19 19:17

### Session Goal
- Add explicit multi-workspace support so users can create and switch between separate conversation graphs.
- Move beyond the single implicit default workspace flow.

### Planned Tasks
- inspect the current workspace loading path and identify the changes needed for workspace-specific routes
- add backend support for listing, creating, and resolving workspaces by slug
- update the page UI so users can switch workspaces and create a new workspace from the app
- verify the new workspace behavior with tests and local Django checks

### Work Completed
- Session started; current branch, repository state, `AGENTS.md`, and progress log were reviewed.
- Confirmed the current implementation still hardcodes a single default workspace in the view layer.
- Added workspace-specific routes so each graph can be opened by its own slug.
- Added backend support for listing workspaces, creating new workspaces, and generating unique workspace slugs.
- Updated the page UI with a workspace switcher and a create-workspace form.
- Kept node creation, editing, and streaming bound to the currently selected workspace slug.
- Added tests for homepage workspace redirect, workspace creation, and workspace-specific graph rendering.
- Verified the implementation with `python3 manage.py check` and `python3 manage.py test`.

### Files Changed
- `docs/agent-progress.md`
- `tree_ui/services/workspace_service.py`
- `tree_ui/static/tree_ui/css/app.css`
- `tree_ui/static/tree_ui/js/app.js`
- `tree_ui/templates/tree_ui/index.html`
- `tree_ui/tests.py`
- `tree_ui/urls.py`
- `tree_ui/views.py`

### Git Workflow
- Current branch at session start: `feature/edit-node-rebranch`
- New branch created/switched: `feature/multi-workspace-support`
- Commits made:
  - none yet in this session
- Push status:
  - not pushed yet in this session

### Current Status
- Users can now create separate workspaces and switch between them explicitly.
- Each workspace has its own graph route and isolated node operations.

### Next Recommended Step
- Evolve the selected node into the future node-focused chat view described in `AGENTS.md`.
- After that, add manual node dragging with persisted positions and graph zoom.

### Known Issues / Blockers / Tech Debt
- `AGENTS.md` is now tracked and should stay aligned with implementation decisions.

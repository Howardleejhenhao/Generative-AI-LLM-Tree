# AGENTS.md

## Project Overview

Project name: **LLM-Tree**

This project is a custom ChatGPT-like web application built with **Python Django**, rendered with **Django Templates**, and started with **Docker Compose**.

The core idea of LLM-Tree is to turn chat history into a **branchable conversation graph** shown in a **DAG-style node editor UI**.

Unlike traditional linear chat applications, this system must allow the user to:

- represent a node as either:
  - a single conversation turn, or
  - a bundled sequence of multiple messages
- continue a conversation from **any existing node**
- create a **new branch** from any node
- choose the **LLM model per newly created node**
- support both **OpenAI** and **Gemini**
- edit an old node and branch again from the edited state
- support **streaming responses**
- preserve branch-local context

---

## Product Requirements

### Core Concept

LLM-Tree is a graph-based conversational interface.

Each node on the canvas represents a conversation unit. A node may contain:

- one prompt + one answer
- or a short sequence of multi-turn messages

Users can click any node and continue from that point, generating a new child branch.

When the user clicks a node, the product should ultimately support a **node-focused conversation view**.
That view should feel like a real LLM chat session:

- the selected node opens into its own conversation workspace/view
- the full ordered message sequence inside that node is visible
- there is a normal chat-style input area at the bottom
- the user can continue chatting inside that node context from that view
- that node-focused view and the graph view should work together rather than replacing the graph concept

### Required Features

#### 1. DAG-style conversation canvas
- The main UI should visually look like a **node editor / DAG editor**
- Nodes and edges should be displayed on a canvas-like area
- Users should be able to:
  - view nodes
  - select nodes
  - inspect node content
  - create child nodes from any node
- Users should also eventually be able to:
  - drag nodes to manually reposition them
  - pan around the graph
  - zoom in and out of the graph
- The UI may look like a DAG editor, but for MVP the underlying conversation lineage can be implemented as a **single-parent branching tree**
- Do **not** implement multi-parent merge logic unless it is easy and stable

#### 2. Flexible node structure
- A node is **not restricted** to exactly one user message and one assistant message
- A node may contain:
  - a single exchange
  - or a short sequence of ordered messages
- Each node should store a message list with role and content

#### 3. Branching from any node
- The user must be able to select any existing node and continue the conversation from there
- Creating a continuation from a historical node must create a **new branch**
- Existing branches must remain unchanged

#### 4. Per-node model selection
- Every time a new node is created, the user must be able to choose which model to use
- Model selection is **per new node**, not per whole branch
- Required providers:
  - OpenAI
  - Gemini

#### 5. Streaming response
- Streaming is a **required feature**
- Assistant generation for a new node must support incremental output
- The UI should show tokens/text appearing progressively instead of only showing the final completed response

#### 6. Edit old node and re-branch
- A user must be able to edit an old node
- After editing, the user must be able to create a new branch from that edited state
- The original historical node/branch should remain preserved unless explicitly replaced
- Prefer a version-safe approach that avoids destructive overwrite

#### 7. Branch-local memory
- When generating a new child node, context must be built from the **current lineage/path only**
- Do **not** include messages from sibling or unrelated branches
- The context rule should be:

  `root -> ... -> selected node -> new prompt`

- This should be treated as the short-term memory rule of the system

#### 8. Security and secrets
- API keys must be stored only in `.env`
- Never hardcode secrets
- Never commit secrets
- Environment variables must be loaded through Django settings / Docker Compose environment config

#### 9. Dockerized startup
- The project must run via **Docker Compose**
- The standard development flow should be:

  - build containers
  - run migrations
  - start Django

- The final project should be easy to start for demo/testing

#### 10. Node-focused conversation view
- Clicking a node should ultimately allow the user to enter a dedicated conversation view for that node
- That view should display the node's internal ordered messages like a normal chat transcript
- The bottom of that view should contain a chat-style input box for continuing the conversation
- Continuing the conversation from that node-focused view must still preserve branch-local context rules

#### 11. Manual node positioning
- Graph nodes should ultimately be movable by mouse drag
- Automatically assigned positions are acceptable as defaults, but users must be able to override them manually
- Updated node positions should persist so the graph layout remains stable after refresh

#### 12. Full-page zoomable graph workspace
- The graph should ultimately occupy the main website experience rather than feeling like a small embedded panel
- The graph view should support zooming so users can inspect large conversation trees comfortably
- The overall layout should prioritize the graph as the primary interface surface

---

## Technical Constraints

### Stack
- Backend: **Python Django**
- Frontend: **Django Templates + JavaScript**
- Container: **Docker / Docker Compose**
- Database: choose a practical default suitable for Django development
- LLM Providers:
  - OpenAI
  - Gemini

### Frontend Approach
Because this project uses Django Templates, the implementation should follow these rules:

- Use Django Templates for page rendering
- Use JavaScript for interactive node/canvas behaviors
- Keep JavaScript modular and maintainable
- Do **not** bury all logic directly inside HTML templates
- Prefer separate static JS files for:
  - canvas rendering
  - node interaction
  - API calls
  - streaming handling
- Plan for the frontend to support both:
  - a graph-first canvas workspace
  - a node-focused chat view for the selected node

### Backend Approach
- Use Django as the main application framework
- Keep provider integrations behind a clean abstraction layer
- Do **not** scatter provider-specific code throughout views/templates
- Prefer service-style modules for:
  - OpenAI generation
  - Gemini generation
  - context construction
  - branch/node creation

### Local Environment Note
A pyenv environment is available and may be activated with:

```bash
pyenv activate LLM-Tree
````

This is optional. Docker Compose remains the primary expected way to run the project.
The coding agent may use the pyenv environment for local checks if helpful, but should not depend on pyenv-only execution.

---

## Suggested Data Model Direction

The exact schema may evolve, but the implementation should roughly support these entities:

### Project / Workspace

Represents one conversation graph/canvas.

### Node

Represents one graph node.
Suggested fields may include:

* id
* project/workspace reference
* parent node reference
* title or summary
* provider
* model name
* position x/y
* created_at / updated_at
* edit/version metadata

### Message

Represents ordered messages inside a node.
Suggested fields may include:

* node reference
* role (`system`, `user`, `assistant`)
* content
* order index
* timestamps

### Edge

Represents parent-child relationships for visual rendering.

For MVP, a single-parent model is enough.

---

## UX Expectations

The UI should make the project feel meaningfully different from a normal chat app.

### Required UX ideas

* Graph/canvas area for nodes and edges
* Side panel or detail panel to inspect selected node content
* Button/action to create child node from selected node
* Model selector when creating a node
* Visible loading/streaming state while generation is in progress
* Ability to edit an old node and branch again
* Ability to open a node into a focused chat-like conversation view
* Ability to drag nodes to reposition them
* Ability to zoom the graph and navigate large trees comfortably
* The graph should eventually dominate the main page layout instead of feeling secondary

### Nice-to-have if easy

* node summary
* color/style differences by model provider
* timestamps
* token usage
* response latency
* mini-map or zoom controls

---

## Session Workflow Rules for the Coding Agent

The coding agent must behave as an iterative project builder across multiple sessions.

### Immediate execution rule

When the user gives a new task such as "請進行新的工作", the agent must **start working immediately**.
The agent must not stall, must not ask unnecessary high-level restatement questions, and must not wait for permission if the requested work is already clear from the repository state, this AGENTS.md file, and the existing progress log.

The agent should:

* first inspect the repository state
* read this `AGENTS.md`
* read the dedicated progress log file
* determine the next concrete action
* then implement the requested work directly

### Before doing any work in a new session

The agent must first read:

* this `AGENTS.md`
* the dedicated progress log file
* the repository state
* the current git status and active branch

The agent must understand:

* what has already been completed
* what is currently in progress
* what should be done next
* what technical decisions were already made

The agent must **not** start blindly.

### At the beginning of each session

The agent must update the dedicated progress log file and explicitly define:

* session date/time if practical
* session objective
* planned tasks
* expected deliverables

### At the end of each session

The agent must update the dedicated progress log file with:

* what was completed
* what files were changed
* what remains unfinished
* what the next recommended step is
* any blockers / bugs / technical debt
* git branch used
* commit hashes and commit messages created in the session
* whether push was completed

### Dedicated progress log requirement

The agent must create and maintain a **separate Markdown file** for persistent progress tracking.

The progress log must **not** be stored directly inside `AGENTS.md`.

Recommended filename:

* `docs/agent-progress.md`

If that file does not exist yet, the agent should create it at the start of the first working session.

### Persistence rule

The dedicated progress log file is the persistent memory for development progress across sessions.

Before any implementation work in a new session, the agent must read the latest entries in that file first.

---

## Git Workflow Rules

The repository already has git initialized.

The coding agent is expected to manage git workflow directly and rigorously.

### Non-negotiable git responsibilities

The agent must:

* inspect current git status before starting significant work
* inspect current branch before creating a new one
* create/switch to an appropriate branch before implementation unless the task is explicitly a tiny docs-only hotfix
* make logically grouped commits
* write meaningful commit messages
* push the working branch when a meaningful session milestone is reached
* record branch / commit / push results in the dedicated progress log file

### Strict git discipline

The agent must be **rigorous** about branch, commit, and push behavior.

Rules:

* do not mix unrelated changes in one commit
* do not make vague commits like `update`, `fix stuff`, `changes`
* do not stay on the wrong branch if the work clearly belongs on a feature/fix/docs branch
* do not rewrite unrelated history unless explicitly required
* do not force push unless absolutely necessary and explicitly justified in the dedicated progress log file
* do not commit secrets, `.env`, local database files, or temporary artifacts
* keep commits small enough to be understandable, but large enough to represent meaningful progress

### Required branch naming style

Use clear names such as:

* `feature/ui-node-canvas`
* `feature/provider-openai-gemini`
* `feature/streaming-node-generation`
* `feature/edit-node-rebranch`
* `fix/canvas-node-selection`
* `docs/update-agent-progress`

### Required commit message style

Prefer conventional, descriptive commit messages such as:

* `feat: add initial node graph canvas UI`
* `feat: implement OpenAI and Gemini provider abstraction`
* `feat: support streaming response generation`
* `feat: allow editing node and re-branching`
* `fix: correct lineage context builder`
* `docs: update agent progress log`

### Push expectations

* Push after a meaningful work unit is completed
* Do not leave substantial completed work only in local commits without good reason
* If push is not possible, explicitly record why in the dedicated progress log file

---

## Delivery Expectations

The human user's role is mainly to run the project and check whether the implemented features match the intended behavior.

Therefore, the coding agent should act with strong ownership and avoid unnecessary back-and-forth.

The agent should:

* make reasonable implementation decisions
* keep the project runnable
* keep progress documented in the dedicated progress log file
* keep git history organized
* prioritize working features over overengineering

---

## MVP Priority Order

When deciding what to build first, prioritize in this order:

1. Django project structure and Docker Compose startup
2. basic data models for project/node/message/edge
3. Django template page for graph view
4. JavaScript-based node/canvas rendering
5. create/select node flow
6. OpenAI/Gemini provider abstraction
7. per-node model selection
8. branch-local context building
9. streaming response support
10. edit old node and re-branch
11. node-focused conversation view
12. manual node dragging and persisted layout positioning
13. graph zoom and full-page workspace refinement
14. progress documentation and cleanup
15. polish/demo readiness

---

## Non-Negotiable Rules

* Use **Django Templates**, not a separate SPA frontend
* Support **OpenAI + Gemini**
* Support **streaming**
* Support **branching from any node**
* Support **editing old nodes and branching again**
* Keep memory **branch-local**
* Store secrets only in `.env`
* Never hardcode API keys
* Start the project with **Docker Compose**
* Create and maintain a separate Markdown progress log file
* Read the progress log file before starting new work
* Update the progress log file at the beginning and end of every session
* Use git properly and rigorously: inspect status, create/switch branch, commit clearly, push appropriately

---

## Definition of Done for the Project

The project is considered functionally successful when:

* it runs through Docker Compose
* the main page is served by Django
* the UI shows a graph/node-editor-style conversation view
* the user can create branches from any node
* a new node can choose between OpenAI and Gemini
* model output streams into the UI
* old nodes can be edited and re-branched
* context only follows the selected branch lineage
* a selected node can open into a dedicated chat-style conversation view
* graph nodes can be manually repositioned
* the graph supports zoom and acts as the primary workspace surface
* secrets are safely handled through `.env`
* project progress is documented and continuously updated in the dedicated progress log file
* git workflow has been actively and rigorously used during development

---

## Final Guidance to the Coding Agent

Build a practical, demoable, maintainable MVP.

Do not overcomplicate the first version.

Favor:

* correctness
* clarity
* incremental delivery
* clean documentation
* working Docker startup
* visible branching and model comparison
* a graph workspace that can eventually expand to a full-page, zoomable, draggable interface

This project should feel like a real experimental LLM conversation tree tool, not just a standard chat clone with cosmetic changes.

---

## Dedicated Progress Log Template

The agent must create and use a separate Markdown file, preferably:

* `docs/agent-progress.md`

The file should follow this template:

```md
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

## Session YYYY-MM-DD HH:MM

### Session Goal
- ...

### Planned Tasks
- ...
- ...

### Work Completed
- ...

### Files Changed
- `path/to/file`
- `path/to/another_file`

### Git Workflow
- Current branch at session start: `...`
- New branch created/switched: `...`
- Commits made:
  - `hash` - `message`
  - `hash` - `message`
- Push status:
  - pushed to `origin/<branch>`
  - or not pushed, reason: `...`

### Current Status
- ...

### Next Recommended Step
- ...

### Known Issues / Blockers / Tech Debt
- ...
```

### Initial log entry to create

When the progress log file is first created, initialize it with content like:

```md
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

## Session Initial

### Session Goal
- Project has not started yet.
- The next coding session should initialize the repository work for LLM-Tree and begin implementation immediately when asked.

### Planned Tasks
- inspect current repository structure
- inspect git status and active branch
- create or switch to an appropriate working branch
- scaffold Django project if not already present
- add Docker Compose based startup if not already present
- begin the first MVP slice according to the priority order above
- update this progress log with real implementation results

### Work Completed
- No coding work has been completed yet in this progress log.

### Files Changed
- `AGENTS.md` created/updated as the primary agent instruction file
- `docs/agent-progress.md` should be created in the first working session

### Git Workflow
- Current branch at session start: unknown
- New branch created/switched: not yet recorded
- Commits made:
  - none recorded yet
- Push status:
  - not yet recorded

### Current Status
- Requirements and workflow expectations are defined.
- Project implementation is expected to begin in the next session immediately upon request.

### Next Recommended Step
- Start the first implementation session immediately:
  - inspect repo
  - inspect git
  - create/switch branch
  - scaffold or verify Django + Docker Compose
  - create `docs/agent-progress.md`
  - update that file with actual progress

### Known Issues / Blockers / Tech Debt
- No implementation status has been recorded yet.
- Actual repository contents are still unknown to the agent until the next working session begins.
```

```

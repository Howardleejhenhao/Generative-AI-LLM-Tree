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

### Optional delegation / review mode

Sometimes the human user may explicitly ask the coding agent to **not implement immediately**, but instead:

* analyze the requested task in detail
* list the next implementation steps clearly
* describe how the work should be implemented
* provide enough concrete guidance so another agent can execute it

In that situation, the coding agent must switch into a **task breakdown + review** mode for that request.

When the user explicitly requests this mode, the agent should:

* produce a detailed implementation plan
* identify the relevant files, services, views, templates, tests, and data flow that should be changed
* describe expected acceptance criteria and verification steps
* include the other agent's expected working environment in the handoff prompt, including at minimum:
  * repository path / current working directory
  * expected branch or branch policy
  * relevant runtime assumptions such as Docker Compose / Django / test commands when applicable
* avoid starting code changes unless the user also explicitly asks for direct implementation

After another agent completes the work and the user returns with the result, the coding agent should:

* inspect the repository changes carefully
* verify whether the requested work was completed correctly
* identify bugs, omissions, regressions, or mismatches
* update the dedicated progress log file on behalf of the project workflow
* if the work is acceptable, handle the final integration personally rather than delegating merge responsibility back to the other agent

Rules for delegated implementation handoffs:

* the handoff prompt must explicitly state that the other agent is **not allowed to merge**
* the handoff prompt must explicitly state that the other agent is **not allowed to modify** `docs/agent-progress.md`; that file is maintained only by this coding agent during review / integration
* the handoff prompt must explicitly state that the other agent is **not responsible for git operations**; branch creation, commit creation, push, merge, and other final git workflow steps are handled by this coding agent
* the other agent may implement, test, and report results, but must leave final approval and merge decisions to this coding agent
* after review is complete and the work is confirmed correct, this coding agent is responsible for merging the accepted changes back into `main`

Default rule:

* unless the user explicitly asks for this delegation-oriented planning mode, the coding agent should still follow the normal immediate execution rule and implement the work directly

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
* treat direct implementation as the default behavior unless the user explicitly asks for a handoff plan for another agent
* when such a handoff plan is explicitly requested, act as the spec author / reviewer first and the progress log maintainer afterward
* when other agents are used for implementation, require them to stop short of merge and keep final review / merge ownership in this coding agent

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

````

---

# V2 Milestone Addendum

This section is an additive extension to the existing project rules above.

The coding agent must treat all previous sections as still active unless this v2 addendum provides a more specific instruction for the new milestone.

The existing AGENTS.md contents above are intentionally preserved.
This addendum extends the project into a more advanced milestone without deleting the original project identity.

---

## V2 Project Overview

### New milestone identity

The project must now be treated as:

**LLM-Tree v2: a multimodal memory agent workspace built on top of a branching conversation graph**

The v2 goal is not only to show branching chat.
The v2 goal is to turn the graph into a practical AI workspace where each node may act like an agent checkpoint with:

- branch-local short-term memory
- retrievable long-term memory
- multimodal inputs
- automatic model routing
- tool use
- MCP-compatible integration path
- demo-ready observability and traceability

### High-level product statement

LLM-Tree v2 should feel like:

**a branching multimodal agent workspace with persistent memory, visible routing, and tool-assisted reasoning**

It must not feel like a normal chatbot with a graph drawn around it.

### Product identity rule

The graph remains the primary product identity.

Do not drift into a purely linear chat product.
Do not treat the graph as secondary decoration.

All new v2 features should strengthen the graph-first concept:

- memory should be aware of workspace vs branch scope
- multimodal input should be attachable to nodes and branches
- routing should be explainable per generation path
- tools should be visible in the reasoning workflow
- comparison should make sense across nodes or branches

---

## V2 Milestone Goals

This milestone must implement or clearly prepare the following major capabilities:

1. long-term memory
2. multimodal support
3. auto routing between models
4. tool use and MCP
5. useful graph-native extensions
6. GitHub Project v2 organization
7. E3P-ready deliverables

These are required milestone targets, not loose optional ideas.

---

## V2 Product Requirements

### 1. Long-term memory

The system must support long-term memory in addition to the existing branch-local short-term memory.

#### Memory design principles

- The current short-term memory rule must remain unchanged
- Short-term memory must still only follow the selected lineage
- Long-term memory must be a separate retrieval layer
- Long-term memory must not silently replace the branch-local context rule
- Sibling branch transcript content must not be injected into prompts unless it has been explicitly saved as memory

#### Non-negotiable short-term rule

The system must continue to treat short-term context as:

`root -> ... -> selected node -> new prompt`

This rule must remain valid even after long-term memory is added.

#### Required long-term memory scopes

The system must support two long-term memory scopes:

##### Workspace memory
Shared across the whole workspace.

Suitable for:
- user preferences
- stable project context
- recurring instructions
- persistent facts
- reusable artifacts

##### Branch memory
Relevant only to one branch or one branch lineage.

Suitable for:
- local assumptions
- branch-specific conclusions
- temporary plans
- branch-only discoveries
- branch-specific summaries

#### Required long-term memory capabilities

The system must support:

- saving memory from conversation content
- manually pinning a message or extracted content into memory
- automatic or semi-automatic memory extraction when appropriate
- retrieving relevant memories before generation
- making retrieved memory visible enough for debugging and demo use
- preserving the difference between:
  - short-term branch context
  - long-term retrieved memory

#### Recommended memory types

The schema may evolve, but should support clear memory categories such as:

- `fact`
- `preference`
- `summary`
- `task`
- `artifact`

#### Required user-facing memory behavior

The user should be able to understand:

- what memory exists
- where it came from
- whether it belongs to workspace scope or branch scope
- which memories were retrieved for a given answer

Long-term memory must be a visible system component, not a hidden claim.

#### Memory implementation direction

The preferred design is to store explicit memory records.
Do not approximate long-term memory by stuffing the whole database into prompts.

---

### 2. Multimodal support

The system must support multimodal input.

For this milestone, the explicit delivery priority is:

**image-first multimodal support**

#### Scope control rule

Focus first on:

- image upload
- image display or indication
- image-aware generation
- image-aware routing
- image-based branching workflows

Do not expand v2 scope aggressively into audio, video, or large general file-processing pipelines unless image-first delivery is already stable.

#### Required multimodal capabilities

The system must support:

- attaching image files to node or node-chat interactions
- storing image attachment metadata
- showing that a node/message has attachments
- allowing supported models/providers to reason about the attached image
- preserving attachment relevance across the correct node/branch flow
- keeping enough metadata visible for debugging and demo use

#### Required multimodal UX expectations

The user should be able to do flows such as:

- create an image-anchored analysis node
- branch from an image-analysis node using different models
- compare responses across multiple branches for the same image
- continue reasoning about the same visual context in child branches

#### Data-structure direction

For the first stable version, prefer a clean attachment layer such as a `NodeAttachment`-style model rather than forcing all message content into a highly complex unified multimodal JSON schema immediately.

The implementation may evolve later, but v2 should prioritize stable delivery over premature abstraction complexity.

---

### 3. Auto routing between models

The system must support automatic routing between models.

However, the routing system must be transparent and controllable.

#### Routing philosophy

Auto routing is an intelligence layer.
It is not allowed to become opaque automation that removes user control.

#### Required routing modes

The system must support at least:

- `manual`
- `auto-fast`
- `auto-balanced`
- `auto-quality`

#### Required routing inputs

The routing layer may consider signals such as:

- whether the request includes image input
- estimated prompt size or complexity
- whether tool usage is expected
- whether a shorter or longer answer is better
- provider/model capability availability
- user-selected speed vs quality mode

#### Required routing outputs

For routed generations, the system must record and preferably surface:

- chosen provider
- chosen model
- routing mode
- high-level reason for the routing decision

Examples of valid reason styles:

- image input detected, so a vision-capable model was selected
- short text-only request in fast mode
- tool-required path preferred a model/provider better suited for orchestration
- high-quality mode preferred a higher-capability model

#### Required override rule

Manual selection must remain available.
Users must still be able to explicitly choose provider/model in appropriate flows.

#### Required observability rule

If routing is enabled, the decision must be inspectable later.
Do not make the decision disappear after generation.

---

### 4. Tool use and MCP

The system must support tool use and prepare for MCP-compatible integration.

#### Required architecture order

The implementation order must be:

1. internal tool contract / registry
2. internal tool invocation flow
3. visible tool traces
4. MCP-compatible adapter layer

Do not jump straight into a vague “supports MCP” claim without having usable internal tool orchestration first.

#### Required internal tool types

The system should implement useful internal tools such as:

- workspace memory search
- branch memory lookup
- node or branch summary
- branch comparison
- attachment lookup
- workspace knowledge lookup
- routing explanation lookup

The exact first set may evolve, but the system must include real tools, not placeholder labels.

#### Required tool invocation behavior

The agent/tool orchestration layer should be able to:

- decide whether a tool is needed
- call the tool
- obtain the tool result
- synthesize a final answer using tool output
- surface enough of that process for debug/demo use

#### Required tool trace visibility

The UI or inspectable metadata must make it possible to understand:

- which tool was used
- whether the call succeeded
- what the tool returned at a high level
- how the final answer relied on that result

Do not hide all tool activity entirely inside backend logs.

#### MCP requirement for this milestone

For v2, it is acceptable if MCP support is implemented as:

- a clear MCP-compatible abstraction
- one or a few demonstrable integration points
- a clean path for future expansion

It is **not** necessary to connect many external servers immediately.
It **is** necessary to design the architecture so MCP is a real direction, not a buzzword.

---

### 5. Additional useful graph-native functions

To make the project more creative and better aligned with the graph identity, v2 must include at least some useful graph-native enhancements beyond the headline four features.

#### Recommended required enhancements

##### Branch comparison
The system should support comparison behavior between nodes or branches.

Comparison may include:
- summary differences
- answer differences
- provider/model differences
- memory usage differences
- routing differences
- tool-usage differences

##### Memory inspector
The system should provide a place to inspect memory entries, including:
- memory scope
- memory type
- memory source
- saved content or summary
- last retrieval or retrieval count if implemented

##### Demo workspace or showcase scenario
The system should maintain a demo-friendly scenario that helps demonstrate:
- graph branching
- image-first multimodal interaction
- long-term memory retrieval
- auto routing
- tool use or MCP direction

The purpose is to make the final 3–5 minute demo efficient and reliable.

---

## V2 Technical Constraints and Architecture

### V2 architecture principle

Do not rewrite the project into a different stack or a separate SPA.

The current graph-first Django architecture remains the foundation.

The v2 milestone should extend the system through clean new layers, not by discarding the original architecture.

### Required architecture layers for v2

The codebase should move toward the following conceptual layers:

1. graph / workspace layer
2. node / message / attachment layer
3. short-term context layer
4. long-term memory retrieval layer
5. routing layer
6. tool orchestration layer
7. provider adapters
8. MCP-compatible adapter layer
9. generation trace / inspectability layer

These do not have to become one-file-per-layer in a rigid way, but the responsibilities should remain clearly separated.

### Backend implementation direction

Prefer service-style modules for:

- memory extraction
- memory retrieval
- multimodal attachment handling
- routing decisions
- tool orchestration
- tool registry
- MCP integration
- generation tracing
- comparison logic

Do not scatter these concerns directly across views.

### Frontend implementation direction

The frontend must continue to follow the existing rule:

- Django Templates for rendering
- JavaScript for interactivity
- modular JS files
- no SPA rewrite

The frontend should gradually support:

- attachment-aware node chat
- routing badges or routing detail
- tool trace visibility
- memory usage visibility
- branch comparison surfaces
- compact but inspectable advanced metadata

### Security direction

Continue using `.env` for secrets only.

Additionally:

- uploaded files must be handled safely
- attachment metadata must not expose secrets or sensitive host paths
- MCP or tool configuration must not hardcode secrets
- demo materials must not expose API keys or private file paths

---

## Suggested V2 Data Model Direction

The exact schema may evolve, but the implementation should roughly support the following additions.

### MemoryRecord

Represents one long-term memory item.

Suggested fields may include:

- id
- workspace reference
- optional branch-related node reference
- source node reference
- scope (`workspace`, `branch`)
- memory type
- title or label
- content
- extracted_summary if useful
- pinned flag
- auto_extracted flag
- retrieval_count
- created_at
- updated_at

### NodeAttachment

Represents an uploaded file attached to a node or message.

Suggested fields may include:

- id
- node reference
- optional message reference
- attachment kind
- storage path or storage key
- mime type
- original filename
- size
- width / height if image
- created_at

### RoutingDecision

Represents how a generation request selected provider/model.

This may be a dedicated model or part of a generation-trace object.

Suggested fields may include:

- source node or generation reference
- routing mode
- chosen provider
- chosen model
- decision reason
- created_at

### ToolInvocation

Represents one tool call executed during generation.

Suggested fields may include:

- source node or generation reference
- tool name
- tool type (`internal`, `mcp`)
- invocation summary
- result summary
- success / failure state
- created_at

### GenerationTrace

If helpful, a dedicated generation trace layer may store:

- routing decision
- retrieved memories
- tool sequence
- final provider/model used
- attachment presence
- final output summary

Do not overengineer this if a lighter implementation is enough, but keep the design extensible.

---

## V2 UX Expectations

The UI must now communicate more than just chat content.

### Required v2 UX visibility

The user should be able to inspect or understand:

- whether long-term memory was used
- which memories were retrieved
- whether the request included attachments
- whether routing was manual or automatic
- which provider/model was actually used
- whether tools were used
- what happened at a high level during tool usage
- how branches differ where comparison is enabled

### UI philosophy for v2

Keep the product visually clean.

Do not bury the graph under many heavy side panels.

Prefer:

- graph-first surfaces
- compact inspector metadata
- expandable advanced traces
- visible but lightweight chips/badges
- demo-friendly clarity
- comparison-first thinking where appropriate

### Nice-to-have if easy

- attachment thumbnails
- memory chips
- routing badges
- tool badges
- trace timeline
- compare mode
- demo mode toggle

---

## GitHub Project v2 Requirement

This milestone must be organized through **GitHub Project v2**.

### Required project-management behavior

The coding agent must:

- keep milestone work aligned to GitHub Project v2 organization
- keep progress-log notes and project status aligned
- use clear issue/task naming that maps to real feature slices
- keep the implementation roadmap understandable from both code and project-management artifacts

### Recommended GitHub Project v2 fields

Use fields such as:

- Status
- Area
- Priority
- Milestone
- Demo Ready
- Risk
- Deliverable Type

### Required milestone areas

Use or maintain areas such as:

- Memory
- Multimodal
- Routing
- Tools/MCP
- UI/UX
- Docs/Demo

### Recommended views

Maintain useful views such as:

- Board by Status
- Table by Area
- Roadmap by Milestone
- Demo Readiness view

### Engineering-management rule

The GitHub Project v2 setup should make the milestone look like a structured engineering effort.
Do not treat it as a cosmetic afterthought.

---

## E3P Deliverables Requirement

This milestone must prepare materials suitable for submission/upload.

### Required deliverables

The project must produce:

1. **One-page system introduction**
2. **System architecture diagram**
3. **Demo video (3 - 5 min.)**

### Deliverable requirements

#### One-page system introduction
This should clearly explain:

- the problem
- the solution idea
- what makes LLM-Tree v2 different
- the key features
- the high-level workflow

It should read like a polished system introduction page, not only a README excerpt.

#### System architecture diagram
This should clearly show major system parts such as:

- browser UI
- Django backend
- workspace / node / message core
- memory subsystem
- routing and tool orchestration
- provider adapters
- MCP-compatible integration layer

#### Demo video
The demo should cover as much of the following as practical in 3–5 minutes:

- graph-based branching workflow
- multimodal image input
- memory save and retrieval
- auto routing
- tool use / MCP direction
- polished project organization and deliverable readiness

### Recommended deliverable storage path

Prefer an organized directory such as:

- `docs/milestone-v2/`
- `docs/milestone-v2/system-introduction.md`
- `docs/milestone-v2/architecture-notes.md`
- `docs/milestone-v2/demo-script.md`
- `docs/milestone-v2/assets/`

The exact filenames may evolve, but deliverable materials must stay structured and easy to maintain.

---

## V2 Session Workflow Addendum

The original session workflow remains active.

The following instructions refine it for the v2 milestone.

### At the beginning of each v2 session

The agent must determine:

- which milestone area the session belongs to
- whether the session is foundational or polish-oriented
- whether the session affects architecture, product behavior, or deliverables
- whether GitHub Project v2 status also needs an update
- whether the session improves final demo readiness

### Preferred implementation style

The agent should work in **cohesive vertical slices**.

A good session slice may include:

- backend/service work
- minimal frontend support
- tests
- progress-log update
- project-management update if relevant
- one meaningful commit
- push after the slice is stable

The goal is meaningful progress, not ceremonial micro-fragmentation.

### At the end of each v2 session

In addition to the original progress-log requirements, the agent should also record when relevant:

- milestone area
- whether GitHub Project v2 status was updated
- whether deliverable documents were updated
- whether demo readiness improved
- whether the slice was foundational, functional, or polish/documentation work

---

## Git Workflow Addendum for V2

The original git workflow rules remain active.

This section refines commit size and branch planning.

### Updated commit granularity rule

The coding agent should prefer:

**one meaningful implementation commit per cohesive feature slice**

This means:

- related backend, frontend, tests, and small docs changes for the same feature may stay in one commit
- the agent does **not** need to split a tightly related feature into many small ceremonial commits
- commit history must remain understandable, but not artificially fragmented

### Good examples

Prefer commit slices like:

- `feat: add workspace and branch long-term memory foundation`
- `feat: support image attachments in node chat`
- `feat: add visible auto-routing decisions`
- `feat: add internal tool orchestration and trace view`
- `docs: add v2 system introduction and demo script`

### Avoid

- splitting one coherent feature into too many tiny commits only for appearance
- mixing unrelated features into one large commit
- keeping finished stable work only in local commits for too long

### Updated push expectation

- Push after a meaningful feature slice is complete
- A single cohesive `commit + push` for a strong session is acceptable and often preferred
- Still document branch, commit, and push results clearly in the progress log

### Recommended v2 branch naming

Use clear names such as:

- `feature/v2-memory-foundation`
- `feature/v2-memory-retrieval-ui`
- `feature/v2-image-attachments`
- `feature/v2-auto-routing`
- `feature/v2-tool-orchestration`
- `feature/v2-mcp-adapter`
- `feature/v2-branch-compare`
- `docs/v2-system-introduction`
- `docs/v2-demo-materials`

---

## V2 Priority Order

For the new milestone, prefer the following implementation order:

1. memory data model foundation
2. workspace memory and branch memory behavior
3. memory save / pin / retrieval flow
4. memory inspector surface
5. image attachment support
6. multimodal-aware provider flow
7. auto routing layer
8. routing visibility and routing trace metadata
9. internal tool registry
10. tool invocation flow and result synthesis
11. tool trace visibility
12. MCP-compatible adapter path
13. branch comparison
14. GitHub Project v2 organization refinement
15. one-page system introduction
16. architecture diagram and notes
17. demo script and final demo polish

This order may be adjusted if implementation dependencies strongly require it, but the milestone direction should remain stable.

---

## Additional Non-Negotiable Rules for V2

- Do **not** break the existing branch-local short-term memory rule
- Do **not** leak sibling-branch transcript content into prompts unless explicitly saved as memory
- Do **not** replace transparent manual model selection with a hidden router
- Do **not** overexpand multimodal scope before image-first support is stable
- Do **not** claim MCP support unless there is a real architecture or integration path in code
- Do **not** hide all tool behavior in backend-only logic
- Do **not** rewrite the project into an SPA
- Do **not** hardcode secrets, local machine paths, or temporary debug credentials
- Do **not** over-fragment commits purely for ceremony
- Do **not** replace the original progress-log workflow; extend it only where useful
- Do **not** delete or rewrite the original contents of this AGENTS.md unless the human user explicitly asks

---

## Definition of Done for V2 Milestone

The v2 milestone is considered functionally successful when:

- the existing graph-first project remains runnable through Docker Compose
- branch-local short-term memory still works correctly
- long-term memory can be stored and retrieved
- memory scope is distinguishable at least between workspace-level and branch-level behavior
- the UI can handle at least image-first multimodal input
- the system can execute manual mode and auto-routing modes
- routing decisions are visible or inspectable
- the system can use internal tools during generation
- the codebase has a practical MCP-compatible integration path
- tool usage is visible enough for demo and debugging
- at least one graph-native enhancement such as branch comparison or memory inspector exists
- GitHub Project v2 is used in a structured way for milestone management
- the one-page system introduction is ready
- the architecture diagram is ready
- the demo flow is ready to be shown in 3–5 minutes
- progress remains documented in the dedicated progress log file
- git history remains organized and understandable without excessive fragmentation

---

## Final Guidance for V2

Build a practical, creative, demo-ready v2 system.

Favor:

- visible intelligence over hidden magic
- traceable memory over vague “smartness”
- multimodal clarity over oversized scope
- transparent routing over mysterious routing
- usable tool orchestration over empty feature claims
- strong demo readiness over unnecessary complexity

The final result should feel like:

**a branching multimodal agent workspace with memory, routing, and tool-assisted reasoning**

not just a chat UI with a few extra options.

---

## Optional Progress Log Extension for V2 Sessions

The original progress log template remains valid.

For v2 sessions, the log may optionally add these sections when useful:

```md
### Milestone Area
- Memory / Multimodal / Routing / Tools-MCP / UI-UX / Docs-Demo

### GitHub Project V2 Update
- updated / not updated
- relevant field or status changes

### Deliverables Impact
- one-page intro updated / architecture notes updated / demo script updated / none

### Demo Readiness Impact
- what became easier to demo after this session
````

These sections extend the original log style.
They should not replace the original required structure.

---

## Practical Execution Bias for Codex

For this v2 milestone, when implementation details are not fully specified by the human user, the coding agent should prefer decisions that are:

1. consistent with the graph-first product identity
2. visible and demoable
3. technically clean but not overengineered
4. compatible with Django Templates + modular JavaScript
5. aligned with the current repository architecture
6. easy to explain in the one-page intro, architecture diagram, and demo video

When in doubt, the agent should choose the option that reduces future ambiguity and reduces the amount of high-level product decision-making that needs to be re-opened later.

The coding agent should act with strong ownership for v2 implementation direction while staying within the constraints defined in this file.

```

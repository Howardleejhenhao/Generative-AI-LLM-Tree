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

## Session 2026-03-19 00:00

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
- Session started; repository state, current branch, and existing files were inspected.

### Files Changed
- `docs/agent-progress.md` created

### Git Workflow
- Current branch at session start: `feature/bootstrap-django-docker`
- New branch created/switched: `feature/bootstrap-django-docker`
- Commits made:
  - none yet in this session
- Push status:
  - not pushed yet in this session

### Current Status
- Repository bootstrap is in progress.

### Next Recommended Step
- Scaffold the Django project and Docker startup files.

### Known Issues / Blockers / Tech Debt
- `docs/agent-progress.md` did not exist before this session.
- Project source code has not been scaffolded yet.

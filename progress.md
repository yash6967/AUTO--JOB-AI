# Project Progress

## Milestone 1: Terminal Boilerplate and Graph Shell

- [x] Create project structure: `agent`, `tools`, `assets`, `server`, `tests`
- [x] Add persistent SQLite LangGraph checkpointer
- [x] Define shared batch state
- [x] Add configurable minimum match score
- [x] Add automatic multi-job queue processing
- [x] Store skipped jobs separately with reasons
- [x] Store applied jobs separately
- [x] Store processing logs and validation notes
- [x] Add deterministic mock job discovery
- [x] Add placeholder approval, tracking, and submission nodes
- [x] Add resume normalization for JSON, PDF, DOCX, TXT, and Markdown
- [x] Add sample structured resume schema
- [x] Add graph-shell tests

### Validation

- `python -m pytest tests/test_graph_shell.py -q`
- Result: `2 passed`
- CLI smoke test confirmed: 2 discovered, 1 pending approval, 1 skipped

## Next Milestones

### Milestone 2: Greenhouse Job Discovery and Parsing

- [x] Add direct Greenhouse board URL configuration
- [x] Support standard `boards.greenhouse.io` URLs
- [x] Support custom Greenhouse domains without company-specific logic
- [x] Fetch and normalize Greenhouse job listings
- [x] Parse job descriptions into structured requirements
- [x] Add Greenhouse integration tests with mocked responses

### Later Work

- [ ] Add Lever integration
- [ ] Add Exa and JSearch integrations
- [ ] Connect Groq structured scoring and document tailoring
- [ ] Add Telegram approval webhook
- [ ] Add Notion tracking
- [ ] Add real email and Playwright submission

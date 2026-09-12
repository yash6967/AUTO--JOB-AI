# Project Progress

This file is the execution checklist for `plan.md`. The plan is complete only
when every unchecked item in this file is complete and the final acceptance
checks pass.

## Architecture and Configuration

- [x] Use Python 3.11+ as the supported runtime.
- [x] Use a terminal/CLI workflow with no frontend UI.
- [x] Use LangGraph for orchestration.
- [x] Use LangChain and Pydantic for LLM workflows and structured data.
- [ ] Use Groq Llama 3.3 70B through `langchain-groq` in live AI nodes.
- [x] Store the normalized profile in local `assets/resume.json`.
- [ ] Use Exa AI SDK for semantic job search.
- [ ] Use JSearch or SerpApi for aggregated job search.
- [ ] Use Playwright for browser scraping and submission.
- [x] Use a persistent SQLite LangGraph checkpointer.
- [ ] Use Telegram Bot API for human approval.
- [ ] Use FastAPI as the Telegram webhook receiver.
- [ ] Use Notion API for application tracking.
- [x] Keep credentials out of source control and document required environment variables.

## Milestone 1: Terminal Boilerplate and Asset Setup

### Asset Preparation

- [x] Create the `assets` directory.
- [x] Define the standard resume schema with `contact`.
- [x] Define the standard resume schema with `summary`.
- [x] Define the standard resume schema with `experience_array`.
- [x] Define the standard resume schema with `skills_list`.
- [x] Define the standard resume schema with `education`.
- [x] Preserve unmatched resume content in `additional_information`.
- [x] Normalize JSON resumes into the standard schema.
- [x] Parse PDF resumes into the standard schema.
- [x] Parse DOCX resumes into the standard schema.
- [x] Parse TXT and Markdown resumes into the standard schema.
- [x] Fail clearly for missing or unsupported resume files.
- [ ] Validate a real user-provided resume in every supported input format.

### State and CLI

- [x] Create the `agent` package.
- [x] Define `hardcoded_criteria` in graph state.
- [x] Define `discovered_jobs` in graph state.
- [x] Define `active_job` in graph state.
- [x] Define `job_description` in graph state.
- [x] Define `match_score` in graph state.
- [x] Define `tailored_materials` in graph state.
- [x] Define `human_decision` in graph state.
- [x] Track `pending_jobs`, `skipped_jobs`, and `applied_jobs`.
- [x] Track processing logs and validation notes.
- [x] Make the minimum match score configurable.
- [x] Create `main.py` as the terminal entry point.
- [x] Initialize the graph and persistent SQLite checkpointer from the CLI.
- [x] Process a shared batch state containing multiple jobs.
- [x] Resume a paused run using the same checkpoint/thread.
- [x] Add deterministic mock discovery and placeholder nodes for shell validation.
- [x] Add graph-shell tests.

### Milestone 1 Acceptance

- [x] CLI starts with the sample resume.
- [x] CLI prints a discovered/pending/skipped summary.
- [x] Low-score jobs are stored separately with reasons.
- [x] Approval resume records an applied job and completes the queue.
- [x] Placeholder integrations produce structured validation notes.

## Milestone 2: Automated Job Discovery

### Search Criteria and Queue

- [x] Configure target roles, including Software Development Engineer.
- [x] Configure target roles, including Backend Engineer.
- [x] Configure target roles, including Data Engineer.
- [x] Configure locations and remote-only preference.
- [ ] Execute search queries from the configured criteria.
- [ ] Run Exa and JSearch/SerpApi searches in parallel.
- [ ] Standardize every result to title, company, URL, and source.
- [ ] Deduplicate results by normalized URL and job identity.
- [x] Save the deduplicated results to `discovered_jobs`.
- [x] Print a discovery summary to the terminal.

### Milestone 2 Acceptance

- [ ] A configured run returns real listings from the enabled providers.
- [ ] Duplicate listings are represented once in the queue.
- [ ] Provider failures stop the run with a clear error.
- [ ] Search behavior has mocked integration tests.

## Milestone 3: Dynamic Scrape and Parse Router

### URL Routing

- [ ] Pop the next job from the queue as `active_job`.
- [ ] Detect standard Greenhouse URLs.
- [ ] Detect custom Greenhouse domains without company-specific logic.
- [ ] Fetch known Greenhouse job data through a lightweight REST/API path.
- [ ] Detect Lever URLs.
- [ ] Fetch known Lever job data through a lightweight REST/API path.
- [ ] Route all other job pages to headless Playwright extraction.
- [ ] Preserve raw extracted text and source metadata in processing logs.

### Structured Requirement Parsing

- [ ] Send extracted job text to Groq.
- [ ] Use Pydantic structured output through `with_structured_output`.
- [ ] Extract `required_skills`.
- [ ] Extract `years_experience`.
- [ ] Extract `core_responsibilities`.
- [ ] Save the parsed result to `job_description`.
- [ ] Stop clearly when scraping or parsing fails.

### Milestone 3 Acceptance

- [ ] Greenhouse standard URLs pass mocked routing tests.
- [ ] Greenhouse custom domains pass mocked routing tests.
- [ ] Lever URLs pass mocked routing tests.
- [ ] Generic pages pass Playwright routing tests.
- [ ] Structured parser output passes schema validation tests.

## Milestone 4: Match Scoring and Tailoring

### Fit Analysis

- [ ] Load the local normalized `assets/resume.json` profile.
- [ ] Send the profile and `job_description` to Groq.
- [ ] Produce a numeric match score from 0 to 100.
- [ ] Identify matching skills and missing requirements.
- [ ] Route scores below the configured threshold to `Skipped`.
- [ ] Record the low-match reason and print it to the terminal.
- [ ] Continue automatically to the next queued job after a low match.

### Document Tailoring

- [ ] Tailor resume bullet points using matched job keywords.
- [ ] Preserve factual profile information and do not invent experience.
- [ ] Draft a concise targeted cover letter.
- [ ] Save resume and cover letter outputs to `tailored_materials`.
- [ ] Generate clean ATS-formatted PDF documents.
- [ ] Store generated document paths and processing metadata.

### Milestone 4 Acceptance

- [ ] Scoring has mocked Groq tests for valid 0-100 output.
- [ ] Threshold routing has tests for below-threshold and qualifying scores.
- [ ] Tailoring output has tests for required fields and factual preservation.
- [ ] The full queue continues after skipped jobs.

## Milestone 5: Telegram Human-in-the-Loop

### Telegram Alert

- [ ] Configure Telegram bot credentials securely.
- [ ] POST an approval message through the Telegram Bot API.
- [ ] Include job title, company, and match score.
- [ ] Include a cover-letter snippet.
- [ ] Add `Approve & Apply` inline button.
- [ ] Add `Skip` inline button.

### Graph Interruption and Webhook

- [ ] Interrupt before `track_and_submit`.
- [ ] Print `Waiting for mobile approval...` in the terminal.
- [ ] Create `server/webhook.py`.
- [ ] Run a lightweight FastAPI webhook listener.
- [ ] Validate Telegram callback payloads.
- [ ] Convert callbacks into `human_decision` values.
- [ ] Resume the correct graph thread using `graph.update_state()`.
- [ ] Continue the next queued job after approval or skip.
- [ ] Preserve all decisions and events in processing logs.

### Milestone 5 Acceptance

- [ ] A qualifying job sends a Telegram approval request.
- [ ] Approve resumes the paused checkpoint.
- [ ] Skip records `human_skipped` and resumes the queue.
- [ ] Invalid or unknown callbacks stop with a clear error.
- [ ] Telegram webhook behavior has tests.

## Milestone 6: Tracking and Submission

### Notion Tracking

- [ ] Configure Notion credentials and database ID securely.
- [ ] Create a Notion row with company.
- [ ] Create a Notion row with role.
- [ ] Create a Notion row with match score.
- [ ] Create a Notion row with date.
- [ ] Create a Notion row with final `human_decision`.
- [ ] Store job URL and document paths where supported.
- [ ] Update the row after submission.
- [ ] Record Notion failures and stop the run clearly.

### Submission Dispatch

- [ ] Select email submission for email-based applications.
- [ ] Support SMTP or Gmail submission using profile data.
- [ ] Select Playwright submission for web forms.
- [ ] Map standard fields from `resume.json`.
- [ ] Upload the generated resume PDF.
- [ ] Submit only after explicit human approval.
- [ ] Record successful submissions as `Applied`.
- [ ] Print the final success message to the terminal.
- [ ] Continue to the next queued job after a successful submission.
- [ ] Record submission errors and stop the run clearly.

### Milestone 6 Acceptance

- [ ] Approved applications are tracked in Notion.
- [ ] Rejected/skipped applications retain their decision and reason.
- [ ] Email submission passes mocked tests.
- [ ] Playwright submission passes mocked form tests.
- [ ] Successful applications appear in `applied_jobs` with timestamps.
- [ ] The complete batch can finish without losing state.

## Cross-Cutting Quality Checks

- [x] Keep secrets and runtime databases out of version control.
- [ ] Add tests for every external integration using mocked responses.
- [ ] Add tests for persistent checkpoint recovery after process restart.
- [ ] Add tests for malformed provider data and malformed LLM output.
- [ ] Add tests for duplicate jobs and empty search results.
- [ ] Add tests for resume parser validation and unmatched sections.
- [ ] Verify Python 3.11 and Python 3.12 compatibility.
- [ ] Document installation, environment variables, and CLI commands.
- [ ] Document how to run the Telegram webhook.
- [ ] Document how to configure Greenhouse and Lever sources.
- [ ] Run the complete test suite successfully.
- [ ] Run a final mocked end-to-end batch successfully.

## Final Definition of Done

- [ ] Every checkbox above is complete.
- [ ] Every milestone acceptance section passes.
- [ ] A real search can discover jobs, process the queue, and parse requirements.
- [ ] Groq can score jobs and tailor documents.
- [ ] Telegram can pause and resume the correct graph thread.
- [ ] Notion records every finalized decision.
- [ ] Approved applications can be submitted through the selected dispatch path.
- [ ] The final batch state, logs, skipped jobs, and applied jobs are recoverable from SQLite.

# plan.md: Job Application AI Agent Architecture (Terminal + Telegram)

## 1. System Architecture & Tech Stack
* **Execution Environment:** Local Terminal / CLI (No frontend UI).
* **Backend Core:** Python 3.11+, LangGraph, LangChain, Pydantic.
* **LLM Provider:** Groq (Llama 3.3 70B via `langchain-groq`).
* **Profile Storage:** Local JSON file (`/assets/resume.json`) containing structured experience, education, and target tech stack (e.g., Python, FastAPI, PySpark, Snowflake).
* **Job Search Tools:** Exa AI SDK, JSearch / SerpApi.
* **Scraping & Execution:** Playwright (headless browser automation).
* **Human-in-the-Loop (HITL):** Telegram Bot API + FastAPI webhook receiver.
* **State Management:** LangGraph `MemorySaver` (SQLite checkpointer).
* **Database Tracking:** Notion API.

---

## 2. Execution Milestones

### Milestone 1: Terminal Boilerplate & Asset Setup
**Objective:** Initialize the project, convert the master resume to JSON, and define the LangGraph state schema.
1. **Asset Preparation (`/assets/resume.json`):** 
   * Convert the master CV into a highly structured JSON format (keys for `contact`, `summary`, `experience_array`, `skills_list`, `education`).
2. **State Schema (`agent/state.py`):**
   * Define a Pydantic `TypedDict` containing: `hardcoded_criteria` (dict), `discovered_jobs` (list), `active_job` (dict), `job_description` (dict), `match_score` (int), `tailored_materials` (dict), `human_decision` (str).
3. **CLI Entry Point (`main.py`):**
   * Set up a simple terminal script to initialize the graph and SQLite checkpointer.

### Milestone 2: Node 1 - Automated Job Discovery
**Objective:** Search external platforms using predefined criteria and queue candidate jobs.
1. **Hardcoded Search Criteria:** 
   * Configure the node to automatically execute queries for specific target roles (e.g., "Software Development Engineer", "Backend Engineer", "Data Engineer") and locations/remote preferences.
2. **Search Tool Execution:**
   * Run Exa API and JSearch in parallel using the hardcoded roles.
   * Standardize the output into a unified list of job dictionaries (Title, Company, URL, Source).
3. **Queue State:** 
   * Save the deduplicated list to `discovered_jobs` in the graph state and print a summary to the terminal.

### Milestone 3: Node 2 - Dynamic Scrape & Parse Router
**Objective:** Extract structured requirements from the target job URL.
1. **URL Routing logic:**
   * Pop the first job from `discovered_jobs`.
   * Evaluate the URL domain. Route known ATS links (Greenhouse/Lever) to lightweight REST API calls. Route all other domains to a headless Playwright extraction script.
2. **LLM Requirements Parsing:**
   * Pass the extracted raw text to Groq.
   * Use `with_structured_output` to enforce a JSON schema output containing `required_skills`, `years_experience`, and `core_responsibilities`. 
   * Save to `job_description` state.

### Milestone 4: Node 3 - Match Scoring & Tailoring
**Objective:** Evaluate fit against the JSON resume and generate bespoke application materials.
1. **Fit Analysis:**
   * Feed the `job_description` state and the local `/assets/resume.json` to Groq.
   * Calculate a `match_score` (0-100). 
   * **Conditional Edge:** If the score is below 60, mark as "Skipped", print to the terminal, and loop back to Node 2 for the next job.
2. **Document Tailoring:**
   * If the score is 60+, prompt Groq to rewrite the JSON resume bullet points to emphasize matching keywords and draft a concise cover letter. Save outputs to `tailored_materials`.

### Milestone 5: Node 4 - Telegram Human-in-the-Loop
**Objective:** Pause execution and push an interactive approval request to a mobile device.
1. **Telegram Alert Trigger:**
   * Make a POST request to the Telegram Bot API sending the Job Title, Company, Match Score, and a snippet of the tailored cover letter.
   * Attach Inline Keyboard Buttons: **[Approve & Apply]** and **[Skip]**.
2. **Graph Interruption:**
   * LangGraph hits an `interrupt_before=["track_and_submit"]` breakpoint, pausing the agent entirely. The terminal outputs: `"Waiting for mobile approval..."`
3. **FastAPI Webhook Listener (`server/webhook.py`):**
   * A lightweight background FastAPI server catches the Telegram webhook payload when a button is pressed.
   * Extracts the decision and resumes the graph via `graph.update_state()`.

### Milestone 6: Node 5 - Tracking & Submission Execution
**Objective:** Log the finalized action and submit the application.
1. **Notion Database Sync:**
   * Connect to the Notion API. Log a new row with the Company, Role, Match Score, Date, and final `human_decision`.
2. **Submission Dispatch:**
   * If approved: Trigger the appropriate submission tool (e.g., SMTP for email applications, or a Playwright auto-fill script for web portals mapping data directly from `resume.json`).
   * Transition state to `Applied`, print the final success message to the terminal, and loop back to Node 2 for the next queued job.
### **Tech Stack for Pilot**
* **Backend Core:** Python 3.11+, LangGraph, LangChain, Pydantic (for structured outputs).
* **LLM Provider:** OpenAI (GPT-4o) or Anthropic (Claude 3.5 Sonnet).
* **Search Tools & APIs:** Exa AI SDK, JSearch / SerpApi, Jooble API, Playwright (for scraping/submitting).
* **Document Engine:** `pdfkit` or WeasyPrint (for PDF generation), Notion API (database).
* **Frontend:** Streamlit (acting as the Human-in-the-Loop dashboard).
* **Memory:** LangGraph `MemorySaver` (in-memory SQLite checkpointer).

---

### **Milestone 1: Project Setup & State Schema Update**
**Goal:** Create the core folder structure, update the `State` schema for job arrays, and build the graph shell.

1. **Initialize Project & Dependencies:**
   * Dependencies: `langgraph`, `langchain-openai`, `pydantic`, `streamlit`, `playwright`, `exa-py`, `requests`.
   * Structure: `/agent` (LangGraph logic), `/tools` (Search/Scraping APIs), `/ui` (Streamlit), `/assets` (Master profile).
2. **Define State Schema (`agent/state.py`):**
   * Fields: 
     * `search_criteria` (dict: title, tech_stack, location, remote_only).
     * `discovered_jobs` (list of dicts: title, company, url, source, raw_snippet).
     * `active_job` (dict: selected job details).
     * `job_description` (dict: extracted requirements).
     * `master_profile` (str).
     * `match_score` (int).
     * `tailored_resume` (str), `cover_letter` (str).
     * `human_approval` (bool), `status` (str).
3. **Compile Graph Skeleton (`agent/graph.py`):**
   * Define node order: `discover_jobs` $\rightarrow$ `scrape_and_parse` $\rightarrow$ `score_fit` $\rightarrow$ `tailor_documents` $\rightarrow$ `wait_for_approval` $\rightarrow$ `track_and_submit`.
   * Add checkpointer and `interrupt_before=["wait_for_approval"]`.

---

### **Milestone 2: Node 1 - Multi-App Job Finder Node**
**Goal:** Build the tool-calling discovery engine that queries external job services and populates `discovered_jobs`.

1. **Implement Job Search Integrations (`tools/search_tools.py`):**
   * **Exa API Tool:** Query semantic job web pages using natural language (e.g., *"Senior FastAPI developer remote positions posted this week"*).
   * **JSearch / SerpApi Tool:** Query Google Jobs / LinkedIn / Indeed aggregated endpoints for structured listings.
   * **Direct ATS Endpoint Tool:** Fetch open job lists from specific company Greenhouse/Lever boards.
2. **Build `discover_jobs` Node (`agent/nodes.py`):**
   * Reads `search_criteria` from state.
   * Runs search tools in parallel, deduplicates results by URL/company name, and standardizes output JSON.
   * Saves candidate array to `discovered_jobs` in state.

---

### **Milestone 3: Node 2 - Job Scrape & Parse Engine**
**Goal:** Take selected job candidate(s) from `discovered_jobs` and extract granular job details.

1. **Build Playwright & API Parser:**
   * Selects an `active_job` from `discovered_jobs`.
   * If source is an ATS API (Greenhouse/Lever), pull raw JSON payload directly.
   * If source is a web page, use Playwright to extract page DOM text.
2. **LLM Requirement Extraction:**
   * Send text to LLM using Pydantic `with_structured_output`.
   * Extract: `required_skills` (list), `nice_to_have` (list), `years_experience` (int), `role_responsibilities` (list), and `application_form_type` (Email vs Web Form).
3. **Update State:** Save structure into `job_description`.

---

### **Milestone 4: Node 3 - Match Scoring & Gap Analysis**
**Goal:** Compare extracted requirements against the user's master profile.

1. **Load Master Profile:** Read `assets/master_resume.md`.
2. **Execute Fit Evaluation:**
   * LLM compares `master_profile` against `job_description`.
   * Generates a 0–100 `match_score` and an explicit list of key matching skills vs missing requirements.
3. **Conditional Routing Edge:**
   * If `match_score` < 60, automatically mark status as `Skipped (Low Match)` and loop to the next job in `discovered_jobs`.
   * If `match_score` $\ge$ 60, proceed to `tailor_documents`.

---

### **Milestone 5: Node 4 - Document Tailoring Engine**
**Goal:** Generate targeted resume bullet points and cover letter.

1. **Resume Tailoring Prompt:**
   * Rewrite master profile experience items to emphasize matches found in `job_description`.
   * Output Markdown string formatted for ATS compilation.
2. **Cover Letter Generator:**
   * Draft a targeted 3-paragraph cover letter using candidate info and job details.
3. **PDF Renderer:**
   * Compile Markdown outputs into clean ATS-formatted PDFs using `pdfkit` / `WeasyPrint`.

---

### **Milestone 6: Streamlit Control Dashboard (Human-in-the-Loop)**
**Goal:** Build a UI to set search filters, review candidate job batches, and approve tailored materials.

1. **Search Parameter Panel:** UI inputs for desired job titles, tech stack keywords, and locations to initialize the `discover_jobs` node.
2. **Discovered Jobs Gallery:** Render cards for all jobs returned by Node 1 showing Match Scores, company info, and gap analyses.
3. **Approval Interruption Handler:**
   * When paused at `wait_for_approval`, render side-by-side previews of the tailored PDF resume and cover letter.
   * Buttons: **[Approve & Apply]**, **[Edit Draft]**, **[Skip Job]**.

---

### **Milestone 7: Node 5 & 6 - Tracking (Notion) & Submission Execution**
**Goal:** Record decisions in a central Notion database and trigger submission automation.

1. **Notion Database Sync Node:**
   * Create database row: Company, Role Title, Match Score, Job URL, Status (`Ready`, `Applied`, `Rejected`).
2. **Submission Engine (Mock / Playwright):**
   * **Email Applications:** Auto-draft or send email via Python `smtplib` / Gmail tool.
   * **Web Form Applications:** Run a Playwright automation script to pre-fill standard input fields (Name, Email, LinkedIn, Github, Resume File Upload).
3. **Final State Sync:** Update Notion entry status to `Applied`.
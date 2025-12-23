# Course Assessment Generation POC

An advanced, audit-ready assessment generation system powered by Google Gemini, FastAPI, and Streamlit. This POC follows Senior Instructional Designer logic to generate blueprints and questions with detailed pedagogic reasoning.

## Features
- **3 Assessment Types**: Practice (Reinforcement), Final (Certification), and Comprehensive (Cross-course).
- **Multi-Source Content**: Analyzes Transcripts (VTT) and PDFs automatically.
- **Pedagogic Governance**: Strictly follows Bloom's Taxonomy and cognitive difficulty mapping.
- **Explainable-AI**: Every question comes with alignment reasoning (Learning Objectives, Competencies, Bloom's Justification).
- **Exportable Results**: Download assessments in structured JSON or flattened CSV formats.

---

## Getting Started

### Prerequisites
- Python 3.10+
- [Optional] Docker & Docker Compose
- Google Cloud Project with Vertex AI / GenAI API enabled.
- Karmayogi API Key.

### Initial Setup
1. Clone this repository to your local machine.
2. Create a `.env` file in the root directory (see `.env.example`).
3. Place your Google Application Credentials JSON file in the root as `credentials.json`.

### Method 1: Docker (Recommended)
Launch the entire stack (Database + API + UI) with one command:
```bash
docker-compose up --build
```
- **API**: http://localhost:8000
- **UI**: http://localhost:8501

### Method 2: Local Installation (Modular)
1. **Install Dependencies**:
   ```bash
   pip install -e .
   ```
2. **Start the API**:
   ```bash
   export PYTHONPATH=$PYTHONPATH:$(pwd)/src
   uvicorn assessment.api:app --reload
   ```
3. **Start the UI**:
   ```bash
   streamlit run ui/app.py
   ```

---

## Project Structure
- `src/assessment/`: Core package containing API, Generator, Fetcher, and DB models.
- `src/assessment/resources/`: Prompts and Schemas.
- `ui/`: Streamlit frontend.
- `scripts/`: Verification and utility scripts.
- `docker-compose.yml`: Orchestration for Postgres, API, and UI.

---

### 1. `POST /generate`
Triggers the background process to fetch content and generate an assessment.
- **Params**:
  - `course_id` (str): The do_id of the course.
  - `assessment_type` (str): `practice`, `final`, or `comprehensive`.
  - `difficulty` (str): `Beginner`, `Intermediate`, `Advanced`.
  - `total_questions` (int): Number of questions *per type* (total = N * 3).
  - `files` (Optional): Extra PDFs to include in analysis.

### 2. `GET /status/{course_id}`
Returns the current status (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`) and result data if finished.

### 3. `GET /download/{course_id}`
Downloads the assessment as a flattened CSV.

### 4. `GET /download_json/{course_id}`
Downloads the raw structured JSON (Blueprint + Questions).

---

## UI Integration Guide (Custom Frontends)

If you are building a custom frontend (React, Vue, etc.), follow this sequence:

### 1. Triggering Generation
Use `multipart/form-data` to handle optional file uploads.

```javascript
const formData = new FormData();
formData.append('course_id', 'do_12345');
formData.append('assessment_type', 'final');
formData.append('difficulty', 'Intermediate');
formData.append('total_questions', 5);
formData.append('additional_instructions', 'Focus more on module 2');
// Optional: files
// formData.append('files', fileBlob, 'notes.pdf');

const response = await fetch('/generate', { method: 'POST', body: formData });
```

### 2. Implementation of Polling
The `/generate` endpoint is asynchronous. Poll the `/status/{course_id}` endpoint every 3-5 seconds.

| Status | Suggested UI Action |
| :--- | :--- |
| `PENDING` | Show "Queued" or "Initializing" message. |
| `IN_PROGRESS` | Show "Analyzing Content & Generating Assessment..." (Spinner). |
| `COMPLETED` | Hide loader, parse `assessment_data`, and render. |
| `FAILED` | Show error message from the `content` field. |

### 3. Parsing the Response
The `assessment_data` field contains a JSON string (or object) with two main branches:

#### **`blueprint`**
Use this to display the "Audit" or "Design rationale" to the user.
- Fields: `assessment_scope_summary`, `smart_learning_objectives`, `unified_competency_map`.

#### **`questions`**
Contains three arrays: `Multiple Choice Question`, `FTB Question`, and `MTF Question`.
- **MCQ**: Render `options`, then map `correct_option_index` for validation.
- **FTB**: Render text with a text input. Use `correct_answer` for validation.
- **MTF**: Render two matching columns from the `pairs` array.
- **Reasoning**: Every question has a `reasoning` object. Display this in an "info" tooltip or "SME Feedback" toggle to provide transparency.

### 4. Direct Downloads
Provide buttons that link directly to:
- `http://api-url/download/{course_id}` (CSV)
- `http://api-url/download_json/{course_id}` (JSON)

---

## Core Governance Rules
- Hallucination is strictly avoided by anchoring prompts to extracted transcripts and PDFs.
- Difficulty is cognitive, not linguistic.
- MTF questions use balanced pairs (no giveaways).
- MCQ questions avoid "All of the above".

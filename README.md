# Course Assessment Generation POC (v3.1)

An advanced, audit-ready assessment generation system powered by **Google Gemini 2.5 Pro**, FastAPI, and Streamlit. This POC follows Senior Instructional Designer logic (Prompt v3.1) to generate blueprints and questions with detailed pedagogic reasoning.

## Features
- **Model**: Powered by `gemini-2.5-pro`.
- **3 Assessment Types**: Practice (Reinforcement), Final (Certification), and Comprehensive (Cross-course).
- **Multilingual Support**: Supports 10+ Indian languages (Hindi, Tamil, Telugu, etc.).
- **KCM Alignment**: Maps questions strictly to the **Karmayogi Competency Model** (Behavioral/Functional).
- **Explainable-AI**: Every question comes with alignment reasoning (Learning Objectives, KCM Competencies, Bloom's Justification).
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
2. Create a `.env` file in the root directory (see `DEPLOYMENT.md`).
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

## API Documentation (v1)

- **Common Project Path**: `/ai-assment-generation`
- **Interactive Documentation**: `http://localhost:8000/ai-assment-generation/docs`
- **API Base URL**: `http://localhost:8000/ai-assment-generation/api/v1`
- **OpenAPI Schema**: `http://localhost:8000/ai-assment-generation/openapi.json`

### 1. `POST /generate`
Triggers the background process to fetch content and generate an assessment.
- **Form Data**:
  - `course_id` (str): The do_id of the course.
  - `assessment_type` (str): `practice`, `final`, or `comprehensive`.
  - `difficulty` (str): `Beginner`, `Intermediate`, `Advanced`.
  - `total_questions` (int): Number of questions *per type* (total = N * 3).
  - `language` (str): Target language (English, Hindi, etc.).
  - `additional_instructions` (str): SME notes.
  - `files` (Optional): Extra PDFs to include in analysis.

### 2. `GET /status/{course_id}`
Returns current status and result data.

### 3. `GET /download/{course_id}`
Downloads the assessment as a flattened CSV.

### 4. `GET /download_json/{course_id}`
Downloads the raw structured JSON.

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
formData.append('language', 'Hindi');
formData.append('additional_instructions', 'Focus more on module 2');

// Base URL: http://localhost:8000/ai-assment-generation/api/v1
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
- Fields: `assessment_scope_summary`, `smart_learning_objectives`, `unified_competency_map`, `time_appropriateness_validation`.

#### **`questions`**
Contains three arrays: `Multiple Choice Question`, `FTB Question`, and `MTF Question`.
- **Reasoning**: Every question has a `reasoning` object containing:
  - `learning_objective_alignment`
  - `competency_alignment`: Nested object with `kcm` (area, theme, sub_theme) and `domain`.
  - `blooms_level_justification`
  - `relevance_percentage`: 0-100 score.

### 4. Direct Downloads
- `http://api-url/ai-assment-generation/api/v1/download/{course_id}` (CSV)
- `http://api-url/ai-assment-generation/api/v1/download_json/{course_id}` (JSON)

---

## Core Governance Rules
- Hallucination is strictly avoided by anchoring prompts to extracted transcripts and PDFs.
- **KCM Mapping**: All competencies must be sourced from the authoritative KCM Dataset.
- All output text (objectives, questions, reasoning) is generated in the selected language.

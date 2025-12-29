# Course Assessment Generation POC

An advanced, audit-ready assessment generation system powered by **Google Gemini 2.5 Pro**, FastAPI, and Streamlit. This POC follows Senior Instructional Designer logic to generate blueprints and questions with detailed pedagogic reasoning.

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
  - `course_ids` (str): Comma-separated list of do_ids (e.g., `do_123` or `do_123, do_456`).
  - `assessment_type` (Enum): `practice`, `final`, `comprehensive`.
  - `difficulty` (Enum): `beginner`, `intermediate`, `advanced`.
  - `total_questions` (int): Number of questions *per type* (total = N * 3).
  - `language` (Enum): `english`, `hindi`, `tamil`, `telugu`, `kannada`, `malayalam`, `marathi`, `bengali`, `gujarati`, `punjabi`, `odia`, `assamese`.
  - `question_types` (List[str], Optional): `mcq`, `ftb`, `mtf`. Defaults to all.
  - `time_limit` (int, Optional): Time limit in minutes (e.g., 60).
  - `topic_names` (str, Optional): Comma-separated list of priority topics.
  - `blooms_config` (str, Optional): JSON string, e.g., `{"Remember": 20, "Apply": 80}`.
  - `additional_instructions` (str): SME notes.
  - `files` (Optional): Extra PDFs to include in analysis.

**Response**:
```json
{
  "message": "Generation started",
  "status": "PENDING",
  "job_id": "comprehensive_do_123_do_456" // Composite ID for multi-course jobs
}
```

### 2. `GET /status/{job_id}`
Returns current status and result data. Use the `job_id` returned from `/generate`.

### 3. `GET /download/{job_id}`
Downloads the assessment as a flattened CSV.

### 4. `GET /download_json/{job_id}`
Downloads the raw structured JSON.

---

## UI Integration Guide (Custom Frontends)

### v3.2 Update: Strict Validation
The API now enforces strict Enum values for `assessment_type`, `difficulty`, and `language`. Do not send free text (e.g., sending "Hard" instead of "Advanced" will fail).

### Multi-Course (Comprehensive) Logic
For `Comprehensive` assessments:
1. Pass multiple IDs in `course_ids` (e.g. `do_1,do_2`).
2. The system generates a deterministic `job_id` (e.g., `comprehensive_do_1_do_2`).
3. If you call `/generate` again with the same IDs, it will return the **existing** job immediately unless `force=true`.

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

## 🔄 Integration Workflow (Async Handling)

Since assessment generation is a long-running process (LLM latency + file processing), the API is designed to be **Asynchronous**.

### Step 1: Start Generation
Call the `POST /generate` endpoint.
- **Request**: Form data with course IDs and config.
- **Response**: Immediate returns with a `job_id`.
```json
{
  "message": "Generation started",
  "status": "PENDING",
  "job_id": "comprehensive_do_123_do_456"
}
```

### Step 2: Poll for Status
Use the `job_id` to poll the status every 5-10 seconds.
**GET** `{{BASE_URL}}/api/v1/status/{job_id}`

**Response Examples:**
- **In Progress**:
  ```json
  { "status": "IN_PROGRESS", "job_id": "comprehensive_do_123_do_456" }
  ```
  _UI Action: Show a loading spinner or progress bar._

- **Completed**:
  ```json
  { 
    "status": "COMPLETED", 
    "job_id": "comprehensive_do_123_do_456", 
    "assessment_data": { 
      "blueprint": {...}, 
      "questions": {...} 
    }
  }
  ```
  _UI Action: Stop polling. Render content from `assessment_data`._

- **Failed**:
  ```json
  { "status": "FAILED", "error": "Reason..." }
  ```
  _UI Action: Show error message._

### Step 3: Retrieve Results
Once status is `COMPLETED`, the response from `GET /status/{job_id}` will contain the full `assessment_data` JSON. This can be used to **display** the questions in the frontend immediately.

- **For Display**: Use the `assessment_data` field from the `/status` response.
- **For Download (CSV)**: Call `GET {{BASE_URL}}/api/v1/download/{job_id}` to get the CSV file.
- **For Download (JSON)**: Call `GET {{BASE_URL}}/api/v1/download_json/{job_id}` to get the JSON file.

## 📚 API Reference (v1.0)

Base URL: `http://localhost:8000/ai-assment-generation`

### 1. Health Check
- **Endpoint**: `GET /health`
- **Description**: Verify service availability.
- **Response**: `{"status": "healthy", ...}`

### 2. Generate Assessment
- **Endpoint**: `POST /api/v1/generate` (Multipart/Form-Data)
- **Description**: Start an async generation job.
- **Key Parameters**:
  - `course_ids` (List[str]): IDs of courses to process.
  - `assessment_type` (Enum): `practice`, `final`, `comprehensive`.
  - `question_types` (List[str]): `mcq`, `ftb`, `mtf`.
  - `time_limit` (int): Duration in minutes.
  - `blooms_config` (JSON str): Optional Bloom's % map.
- **Response**: `{"status": "PENDING", "job_id": "comprehensive_do_123..."}`

### 3. Check Status
- **Endpoint**: `GET /api/v1/status/{job_id}`
- **Description**: Poll for job progress.
- **Response**: Returns status (`IN_PROGRESS`, `COMPLETED`, `FAILED`).
- **Note**: When `COMPLETED`, the JSON response includes the full `assessment_data` object, which can be used to render the results UI directly.

### 4. Download Results
- **Endpoint (CSV)**: `GET /api/v1/download/{job_id}`
- **Endpoint (JSON)**: `GET /api/v1/download_json/{job_id}`
- **Description**: Download the assessment as a file (CSV or JSON). Only available when status is `COMPLETED`.

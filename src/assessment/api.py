import os
import shutil
import logging
import json
import pandas as pd
from pathlib import Path
from typing import List, Optional, Union
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, HTTPException, APIRouter
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager

from .config import INTERACTIVE_COURSES_PATH
from .db import init_db, create_job, update_job_status, get_assessment_status, save_assessment_result
from .fetcher import fetch_course_data
from .generator import generate_assessment

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler() # Good for Docker/K8s
    ]
)
logger = logging.getLogger("assessment-api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Assessment API...")
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
    yield
    logger.info("Shutting down Assessment API...")

app = FastAPI(
    title="Course Assessment Generator API (v1.0)",
    description="Audit-ready assessment generation using Gemini 2.5 Pro",
    version="1.0.0",
    lifespan=lifespan,
    root_path="/ai-assment-generation",
    servers=[{"url": "/ai-assment-generation", "description": "Default Server"}],
    docs_url="/docs",
    openapi_url="/openapi.json"
)

# Routers
api_v1_router = APIRouter(prefix="/api/v1")

@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ai-assment-generation/docs")

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "assessment-generator"}

@api_v1_router.get("/status/{job_id}")
async def check_status(job_id: str):
    status = await get_assessment_status(job_id)
    if not status:
        return JSONResponse(status_code=404, content={"status": "NOT_FOUND"})
    return status

from enum import Enum
from typing import List, Optional, Dict

class AssessmentType(str, Enum):
    PRACTICE = "practice"
    FINAL = "final"
    COMPREHENSIVE = "comprehensive"

class Difficulty(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class Language(str, Enum):
    ENGLISH = "english"
    HINDI = "hindi"
    TAMIL = "tamil"
    TELUGU = "telugu"
    KANNADA = "kannada"
    MALAYALAM = "malayalam"
    MARATHI = "marathi"
    BENGALI = "bengali"
    GUJARATI = "gujarati"
    PUNJABI = "punjabi"
    ODIA = "odia"
    ASSAMESE = "assamese"

class QuestionType(str, Enum):
    MCQ = "mcq"
    FTB = "ftb"
    MTF = "mtf"

@api_v1_router.post("/generate")
async def generate(
    background_tasks: BackgroundTasks,
    course_ids: List[str] = Form(..., description="List of Course IDs (or comma-separated string)"),
    force: bool = Form(False),
    assessment_type: AssessmentType = Form(...),
    difficulty: Difficulty = Form(...),
    total_questions: int = Form(5),
    question_types: List[str] = Form(["mcq", "ftb", "mtf"], description="List of Question Types"),
    time_limit: Optional[int] = Form(None, description="Time limit in minutes"),
    topic_names: Optional[str] = Form("", description="Comma-separated topics"),
    language: Language = Form(Language.ENGLISH),
    blooms_config: Optional[str] = Form("", description="JSON string of Bloom's %"),
    additional_instructions: Optional[str] = Form(""),
    files: Optional[List[Union[UploadFile, str]]] = File(None)
):
    # Filter out empty strings from files list (handle Swagger/CURL empty inputs)
    valid_files = []
    if files:
        for f in files:
            if isinstance(f, UploadFile):
                valid_files.append(f)
    files = valid_files

    # Sanitize optional string inputs (Swagger sometimes sends "string" or "")
    if topic_names in ["string", ""]: topic_names = None
    if blooms_config in ["string", ""]: blooms_config = None
    if additional_instructions in ["string", ""]: additional_instructions = None
    
    # Parse List Inputs (Support both List[str] and comma-separated string fallback)
    c_ids = []
    for item in course_ids:
        c_ids.extend([c.strip() for c in item.split(",") if c.strip()])
    
    q_types = []
    for item in question_types:
        q_types.extend([q.strip().lower() for q in item.split(",") if q.strip()])
    
    # Validate Question Types
    valid_types = {t.value for t in QuestionType}
    for qt in q_types:
        if qt not in valid_types:
             raise HTTPException(status_code=400, detail=f"Invalid question type: {qt}. Allowed: {valid_types}")

    t_names = [t.strip() for t in topic_names.split(",")] if topic_names else None
    
    # Parse Bloom's Config
    b_dist = None
    if blooms_config:
        try:
            b_dist = json.loads(blooms_config)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON for blooms_config")

    # Composite Key for Caching (Sorted IDs)
    sorted_ids = sorted(c_ids)
    composite_id = f"comprehensive_{'_'.join(sorted_ids)}" if len(sorted_ids) > 1 else sorted_ids[0]

    existing = await get_assessment_status(composite_id)
    if existing and existing['status'] == 'COMPLETED' and not force:
        return {"message": "Assessment already exists", "status": "COMPLETED", "job_id": composite_id}
    
    if existing and existing['status'] == 'IN_PROGRESS':
        return {"message": "Assessment generation in progress", "status": "IN_PROGRESS", "job_id": composite_id}

    await create_job(composite_id)
    
    saved_files = []
    if files:
        # Use first course ID for temp storage to avoid complex path logic
        temp_dir = Path(INTERACTIVE_COURSES_PATH) / sorted_ids[0] / "uploads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        for file in files:
            file_path = temp_dir / file.filename
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_files.append(file_path)

    background_tasks.add_task(
        process_course_task, 
        composite_id, 
        c_ids, 
        saved_files, 
        assessment_type, 
        difficulty, 
        total_questions, 
        additional_instructions, 
        language,
        t_names,
        b_dist,
        q_types,
        time_limit
    )
    return {"message": "Generation started", "status": "PENDING", "job_id": composite_id}

async def process_course_task(
    job_id: str, 
    course_ids: List[str],
    extra_files: List[Path], 
    assessment_type: str, 
    difficulty: str, 
    total_questions: int, 
    additional_instructions: Optional[str], 
    language: str,
    topic_names: Optional[List[str]],
    blooms_distribution: Optional[Dict[str, int]],
    question_types: List[str],
    time_limit: Optional[int]
):
    try:
        await update_job_status(job_id, "IN_PROGRESS")
        
        base_path = Path(INTERACTIVE_COURSES_PATH)
        
        # Fetch Data for ALL courses
        for cid in course_ids:
            success = await fetch_course_data(cid, base_path)
            if not success:
                logger.warning(f"Failed to fetch content for {cid}, proceeding with available data.")

        # 3. Generate Assessment
        metadata, assessment, usage = await generate_assessment(
            course_ids=course_ids,
            assessment_type=assessment_type, 
            difficulty_level=difficulty, 
            total_questions=total_questions,
            additional_instructions=additional_instructions,
            input_language=language,
            topic_names=topic_names,
            blooms_distribution=blooms_distribution,
            question_types=question_types,
            time_limit=time_limit
        )
        
        # 4. Save Result
        await save_assessment_result(job_id, metadata, assessment, usage)
        
    except Exception as e:
        logger.exception(f"Job failed for {job_id}")
        await update_job_status(job_id, "FAILED", str(e))

@api_v1_router.get("/download_csv/{job_id}")
async def download_csv(job_id: str):
    data = await get_assessment_status(job_id)
    if not data or data['status'] != 'COMPLETED':
        raise HTTPException(status_code=404, detail="Assessment not ready or found")
    
    assessment_json = json.loads(data['assessment_data']) if isinstance(data['assessment_data'], str) else data['assessment_data']
    
    # Flatten logic for new structure
    rows = []
    questions_obj = assessment_json.get("questions", {})
    
    for q_type, q_list in questions_obj.items():
        for q in q_list:
            row = {
                "Question ID": q.get("question_id"),
                "Type": q_type,
                "Text": q.get("question_text", "N/A"),
                "Options/Pairs": json.dumps(q.get("options") or q.get("pairs") or ""),
                "Correct Answer": q.get("correct_option_index") if q.get("correct_option_index") is not None else q.get("correct_answer"),
                "Blooms Level": q.get("blooms_level"),
                "Difficulty": q.get("difficulty_level"),
                "Relevance %": q.get("relevance_percentage")
            }
            rows.append(row)
        
    df = pd.DataFrame(rows)
    csv_path = Path(INTERACTIVE_COURSES_PATH) / f"{job_id}_assessment.csv"
    df.to_csv(csv_path, index=False)
    
    return FileResponse(csv_path, filename=f"{job_id}_assessment.csv")

@api_v1_router.get("/download_json/{job_id}")
async def download_json(job_id: str):
    data = await get_assessment_status(job_id)
    if not data or data['status'] != 'COMPLETED':
        raise HTTPException(status_code=404, detail="Assessment not ready or found")
    
    assessment_json = json.loads(data['assessment_data']) if isinstance(data['assessment_data'], str) else data['assessment_data']
    
    json_path = Path(INTERACTIVE_COURSES_PATH) / f"{job_id}_assessment.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(assessment_json, f, indent=2, ensure_ascii=False)
        
    return FileResponse(json_path, filename=f"{job_id}_assessment.json", media_type='application/json')

app.include_router(api_v1_router)

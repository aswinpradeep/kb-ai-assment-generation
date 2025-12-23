import os
import shutil
import logging
import json
import pandas as pd
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, HTTPException
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
    title="Course Assessment Generator API",
    description="Audit-ready assessment generation using Gemini 1.5 Pro",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "assessment-generator"}

@app.get("/status/{course_id}")
async def check_status(course_id: str):
    status = await get_assessment_status(course_id)
    if not status:
        return JSONResponse(status_code=404, content={"status": "NOT_FOUND"})
    return status

@app.post("/generate")
async def generate(
    background_tasks: BackgroundTasks,
    course_id: str = Form(...),
    force: bool = Form(False),
    assessment_type: str = Form("final"),
    difficulty: str = Form("Intermediate"),
    total_questions: int = Form(5),
    additional_instructions: Optional[str] = Form(None),
    files: List[UploadFile] = File(None)
):
    existing = await get_assessment_status(course_id)
    if existing and existing['status'] == 'COMPLETED' and not force:
        return {"message": "Assessment already exists", "status": "COMPLETED"}
    
    if existing and existing['status'] == 'IN_PROGRESS':
        return {"message": "Assessment generation in progress", "status": "IN_PROGRESS"}

    await create_job(course_id)
    
    saved_files = []
    if files:
        temp_dir = Path(INTERACTIVE_COURSES_PATH) / course_id / "uploads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        for file in files:
            file_path = temp_dir / file.filename
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_files.append(file_path)

    background_tasks.add_task(process_course_task, course_id, saved_files, assessment_type, difficulty, total_questions, additional_instructions)
    return {"message": "Generation started", "status": "PENDING"}

async def process_course_task(course_id: str, extra_files: List[Path], assessment_type: str, difficulty: str, total_questions: int, additional_instructions: Optional[str]):
    try:
        await update_job_status(course_id, "IN_PROGRESS")
        
        base_path = Path(INTERACTIVE_COURSES_PATH)
        success = await fetch_course_data(course_id, base_path)
        if not success:
            raise Exception("Failed to fetch course content")
            
        course_folder = base_path / course_id
        
        if extra_files:
            for f in extra_files:
                dest = course_folder / f.name
                if f.exists():
                    shutil.move(str(f), str(dest))

        # 3. Generate Assessment
        metadata, assessment, usage = await generate_assessment(
            course_folder, 
            assessment_type=assessment_type, 
            difficulty_level=difficulty, 
            total_questions=total_questions,
            additional_instructions=additional_instructions
        )
        
        # 4. Save Result
        await save_assessment_result(course_id, metadata, assessment, usage)
        
    except Exception as e:
        logger.exception(f"Job failed for {course_id}")
        await update_job_status(course_id, "FAILED", str(e))

@app.get("/download/{course_id}")
async def download_csv(course_id: str):
    data = await get_assessment_status(course_id)
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
    csv_path = Path(INTERACTIVE_COURSES_PATH) / f"{course_id}_assessment.csv"
    df.to_csv(csv_path, index=False)
    
    return FileResponse(csv_path, filename=f"{course_id}_assessment.csv")

@app.get("/download_json/{course_id}")
async def download_json(course_id: str):
    data = await get_assessment_status(course_id)
    if not data or data['status'] != 'COMPLETED':
        raise HTTPException(status_code=404, detail="Assessment not ready or found")
    
    assessment_json = json.loads(data['assessment_data']) if isinstance(data['assessment_data'], str) else data['assessment_data']
    
    json_path = Path(INTERACTIVE_COURSES_PATH) / f"{course_id}_assessment.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(assessment_json, f, indent=2, ensure_ascii=False)
        
    return FileResponse(json_path, filename=f"{course_id}_assessment.json", media_type='application/json')

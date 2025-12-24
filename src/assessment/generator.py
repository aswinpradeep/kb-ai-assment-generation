import os
import json
import asyncio
import logging
import time
import yaml
import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
from google import genai
from google.genai import types
from google.genai.errors import APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import (
    DB_DSN,
    GOOGLE_PROJECT_ID, GOOGLE_LOCATION, GENAI_MODEL_NAME, 
    GOOGLE_APPLICATION_CREDENTIALS
)

logger = logging.getLogger(__name__)

# Initialize GenAI Client
if GOOGLE_APPLICATION_CREDENTIALS:
    client = genai.Client(
        project=GOOGLE_PROJECT_ID,
        location=GOOGLE_LOCATION,
        vertexai=True
    )
else:
    client = None
    logger.warning("GOOGLE_APPLICATION_CREDENTIALS not set.")

# Load Resources
# Everything is now in the resources/ directory relative to this file
PACKAGE_DIR = Path(__file__).parent
RESOURCE_DIR = PACKAGE_DIR / "resources"

def load_yaml(filename):
    path = RESOURCE_DIR / filename
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}

def load_json(filename):
    path = RESOURCE_DIR / filename
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

ASSESSMENT_PROMPTS = load_yaml('prompts.yaml')
ASSESSMENT_SCHEMA_FILE = load_json('schemas.json')
ASSESSMENT_SCHEMA = ASSESSMENT_SCHEMA_FILE.get('full_schema', {})
KCM_DATASET = load_json('competencies.json')

async def generate_assessment(
    course_folder: Path, 
    assessment_type: str = "final", 
    difficulty_level: str = "Intermediate", 
    total_questions: int = 5,
    time_to_complete: Optional[str] = None,
    additional_instructions: Optional[str] = None,
    input_language: str = "English"
) -> Tuple[Dict, Dict, Dict]:
    """
    Generates assessment for a course folder.
    Returns (metadata, assessment_json, usage_metadata)
    """
    course_id = course_folder.name
    logger.info(f"Generating assessment for {course_id} (Type: {assessment_type})")

    # 1. Load Metadata
    meta_path = course_folder / "metadata.json"
    current_metadata = {}
    if meta_path.exists():
        current_metadata = json.loads(meta_path.read_text(encoding='utf-8'))

    # 2. Load Transcript (and any other text files for SME notes)
    transcript = "N/A"
    vtt_path = course_folder / "english_subtitles.vtt"
    if vtt_path.exists():
        transcript = await extract_vtt_text(vtt_path)
    
    # 3. Load PDFs
    pdf_snippets = []
    for pdf_file in course_folder.glob("*.pdf"):
        text = await extract_pdf_text(pdf_file)
        if text:
            pdf_snippets.append(f"--- PDF: {pdf_file.name} ---\n{text}")
    
    pdf_snippets_str = "\n\n".join(pdf_snippets) if pdf_snippets else "N/A"

    # 4. Build Prompt
    prompt = build_prompt(
        course_id, current_metadata, transcript, pdf_snippets_str,
        assessment_type, difficulty_level, total_questions, time_to_complete,
        additional_instructions, input_language
    )

    # 5. Call LLM
    response_text, usage = await call_llm(prompt)
    
    try:
        result_json = json.loads(response_text)
        return current_metadata, result_json, usage
    except json.JSONDecodeError:
        logger.error("Failed to parse LLM response as JSON")
        raise ValueError("LLM response was not valid JSON")

def build_prompt(
    course_id: str, 
    current_metadata: Optional[Dict[str, Any]], 
    transcript: str, 
    pdf_snippets: str,
    assessment_type: str,
    difficulty_level: str,
    total_questions: int,
    time_to_complete: Optional[str],
    additional_instructions: Optional[str],
    input_language: str
) -> str:
    prompt_template = ASSESSMENT_PROMPTS.get('system_prompt_template', '')
    
    # Simple placeholder replacement
    prompt = prompt_template.replace("{course_id}", course_id)
    prompt = prompt.replace("{metadata}", json.dumps(current_metadata, indent=2))
    prompt = prompt.replace("{content_context}", f"Transcript:\n{transcript}\n\nPDF Extracts:\n{pdf_snippets}")
    prompt = prompt.replace("{additional_instructions}", additional_instructions or "None provided")
    prompt = prompt.replace("{input_language}", input_language)
    prompt = prompt.replace("{kcm_dataset}", json.dumps(KCM_DATASET, indent=2))
    
    prompt = prompt.replace("{assessment_type}", assessment_type)
    prompt = prompt.replace("{difficulty_level}", difficulty_level)
    prompt = prompt.replace("{total_questions}", str(total_questions))
    prompt = prompt.replace("{total_questions_x3}", str(total_questions * 3))
    prompt = prompt.replace("{time_to_complete}", time_to_complete or "Not provided (use standard pacing)")

    # Bloom's distribution (Fixed or derived from assessment_type)
    if assessment_type == "comprehensive":
        blooms_dist = "Apply: 40%, Analyze: 30%, Evaluate: 30%"
    else:
        blooms_dist = "Remember: 20%, Understand: 25%, Apply: 25%, Analyze: 20%, Evaluate: 10%"
    
    prompt = prompt.replace("{blooms_dist}", blooms_dist)
    prompt = prompt.replace("{p_version}", "v3.1")
    prompt = prompt.replace("{a_version}", "api/v1")

    return prompt

@retry(retry=retry_if_exception_type((Exception, APIError)), stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def call_llm(prompt: str) -> Tuple[str, Dict[str, Any]]:
    if not client:
        raise RuntimeError("GenAI client is not initialized.")
        
    logger.info("Calling GenAI model: %s", GENAI_MODEL_NAME)
    
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=ASSESSMENT_SCHEMA, # Use the correct Assessment Schema
        temperature=0.1,
    )

    contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]

    response = await client.aio.models.generate_content(
        model=GENAI_MODEL_NAME,
        contents=contents,
        config=config
    )
    
    llm_usage = {}
    if response.usage_metadata:
        llm_usage = response.usage_metadata.to_json_dict()

    if not response.text:
        raise RuntimeError("LLM returned an empty response text.")
    
    return response.text, llm_usage

async def extract_vtt_text(vtt_path: Path) -> str:
    def _read_and_clean():
        text_lines = []
        try:
            raw = vtt_path.read_text(encoding='utf-8')
        except Exception:
            raw = vtt_path.read_text(encoding='latin-1')
            
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.upper().startswith('WEBVTT') or '-->' in line or line.isdigit():
                continue
            text_lines.append(line)
        return '\n'.join(text_lines)

    return await asyncio.to_thread(_read_and_clean)

def extract_pdf_text_sync(pdf_path: Path) -> str:
    text_parts = []
    try:
        doc = fitz.open(str(pdf_path))
        for page in doc:
            page_text = page.get_text().strip()
            if page_text:
                text_parts.append(page_text)
        doc.close()
    except Exception as e:
        logger.exception('PDF extraction failed for %s: %s', pdf_path, e)
    return '\n\n'.join(text_parts)

async def extract_pdf_text(pdf_path: Path) -> str:
    return await asyncio.get_running_loop().run_in_executor(None, extract_pdf_text_sync, pdf_path)

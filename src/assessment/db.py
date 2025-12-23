import asyncpg
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from .config import DB_DSN

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS interactive_assessments (
    course_id TEXT PRIMARY KEY,
    status TEXT NOT NULL, -- 'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB,
    assessment_data JSONB,
    token_usage JSONB,
    error_message TEXT
);
"""

async def init_db():
    conn = await asyncpg.connect(DB_DSN)
    try:
        await conn.execute(CREATE_TABLE_SQL)
    finally:
        await conn.close()

async def get_assessment_status(course_id: str) -> Optional[Dict[str, Any]]:
    conn = await asyncpg.connect(DB_DSN)
    try:
        row = await conn.fetchrow("SELECT * FROM interactive_assessments WHERE course_id = $1", course_id)
        if row:
            return dict(row)
        return None
    finally:
        await conn.close()

async def create_job(course_id: str):
    conn = await asyncpg.connect(DB_DSN)
    try:
        await conn.execute("""
            INSERT INTO interactive_assessments (course_id, status, updated_at)
            VALUES ($1, 'PENDING', NOW())
            ON CONFLICT (course_id) DO UPDATE
            SET status = 'PENDING', updated_at = NOW(), error_message = NULL
        """, course_id)
    finally:
        await conn.close()

async def update_job_status(course_id: str, status: str, error: str = None):
    conn = await asyncpg.connect(DB_DSN)
    try:
        await conn.execute("""
            UPDATE interactive_assessments
            SET status = $2, error_message = $3, updated_at = NOW()
            WHERE course_id = $1
        """, course_id, status, error)
    finally:
        await conn.close()

async def save_assessment_result(course_id: str, metadata: dict, assessment: dict, usage: dict):
    conn = await asyncpg.connect(DB_DSN)
    try:
        await conn.execute("""
            UPDATE interactive_assessments
            SET status = 'COMPLETED', 
                metadata = $2, 
                assessment_data = $3, 
                token_usage = $4, 
                updated_at = NOW()
            WHERE course_id = $1
        """, course_id, json.dumps(metadata), json.dumps(assessment), json.dumps(usage))
    finally:
        await conn.close()

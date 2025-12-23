import asyncio
import asyncpg
import os
import json
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()
DB_DSN = os.getenv("DB_DSN")
if not DB_DSN:
    raise ValueError("❌ DB_DSN not found in .env file!")

OUTPUT_DIR = "./exports"
os.makedirs(OUTPUT_DIR, exist_ok=True)
CSV_OUTPUT_FILE = os.path.join(OUTPUT_DIR, "latest_s2_courses.csv")


def safe_get(d, path, default=None):
    """Safely fetch nested JSON fields using dot-separated path."""
    try:
        for p in path.split("."):
            if isinstance(d, list):
                d = d[0] if d else {}
            d = d.get(p, {})
        if isinstance(d, (str, int, float)):
            return d
        return d
    except Exception:
        return default

def format_competencies(data, key):
        """Convert list of competency dicts into readable text format."""
        comps = safe_get(data, key, [])
        if isinstance(comps, str):
            try:
                comps = json.loads(comps)
            except json.JSONDecodeError:
                return ""
        if not isinstance(comps, list):
            return ""

        formatted = []
        for c in comps:
            if isinstance(c, dict):
                theme = c.get("Theme") or c.get("theme") or ""
                subtheme = c.get("SubTheme") or c.get("subtheme") or ""
                formatted.append(f"Theme:  {theme}\nSubTheme: {subtheme}")
        return "\n\n-----------\n\n".join(formatted)

async def export_filtered_fields():
    conn = None
    try:
        conn = await asyncpg.connect(DB_DSN)
        print("✅ Connected to PostgreSQL")

        query = """
        SELECT 
            course_id,
            blueprint_json,
            assessment_json,
            llm_usage_json,
            status,
            generated_at
        FROM course_assessment_generated
        WHERE status = 'success';
        """

        rows = await conn.fetch(query)
        print(f"📦 Retrieved {len(rows)} rows")

        extracted_data = []

        for row in rows:
            blueprint = row["blueprint_json"]
            assessment = row["assessment_json"]
            llm_usage = row["llm_usage_json"]

            if isinstance(blueprint, str): blueprint = json.loads(blueprint)
            if isinstance(assessment, str): assessment = json.loads(assessment)
            if isinstance(llm_usage, str): llm_usage = json.loads(llm_usage)
            
            # Extract Token Usage
            total_tokens = 0
            if isinstance(llm_usage, dict):
                total_tokens = llm_usage.get('total_token_count', 0)

            # Handle cases where blueprint might be inside a 'blueprint' key or at root
            bp_root = blueprint.get('blueprint', blueprint) if blueprint else {}
            
            # Extract Blueprint Fields
            course_title = bp_root.get('course_title', '')
            summary = bp_root.get('summary', '')
            competencies = bp_root.get('competencies', {})
            modules = bp_root.get('modules', [])
            learning_objectives = bp_root.get('learning_objectives', [])
            assessment_framework = bp_root.get('assessment_framework', {})
            
            # Format Competencies
            comp_str = ""
            if isinstance(competencies, dict):
                comp_list = []
                for k, v in competencies.items():
                    if isinstance(v, list):
                        comp_list.append(f"{k.capitalize()}: {', '.join(v)}")
                comp_str = "\n".join(comp_list)
            
            # Format Modules
            mod_str = "\n".join([f"{m.get('id', '')}. {m.get('title', '')}" for m in modules]) if isinstance(modules, list) else ""
            
            # Format Learning Objectives
            lo_str = "\n".join([f"- {lo}" for lo in learning_objectives]) if isinstance(learning_objectives, list) else ""
            
            # Format Assessment Framework
            af_str = ""
            if isinstance(assessment_framework, dict):
                af_list = []
                diff = assessment_framework.get('difficulty_levels', [])
                if diff: af_list.append(f"Difficulty: {', '.join(diff)}")
                
                q_types = assessment_framework.get('question_types', {})
                if q_types: 
                    af_list.append("Question Types:")
                    for k, v in q_types.items():
                        af_list.append(f"  - {k}: {v}")
                        
                eval_pol = assessment_framework.get('evaluation_policy', {})
                if eval_pol:
                    af_list.append(f"Passing: {eval_pol.get('passing_criteria', '')}")
                
                af_str = "\n".join(af_list)

            # Format Questions
            questions = assessment.get('questions', []) if assessment else []
            questions_formatted = ""
            for idx, q in enumerate(questions, 1):
                q_text = q.get('question_text', '')
                q_type = q.get('question_type', '')
                q_ans = ""
                if q_type == 'Multiple Choice Question':
                    opts = [f"{o['index']}. {o['text']}" for o in q.get('options', [])]
                    q_ans = f"Options: {', '.join(opts)} | Correct: {q.get('correct_option_index')}"
                elif q_type == 'FTB Question':
                    q_ans = f"Answer: {q.get('correct_answer')}"
                elif q_type == 'MTF Question':
                    pairs = [f"{p['left']} -> {p['right']}" for p in q.get('pairs', [])]
                    q_ans = f"Pairs: {'; '.join(pairs)}"
                
                questions_formatted += f"Q{idx} [{q_type}]: {q_text}\n   {q_ans}\n   Rationale: {q.get('rationale')}\n\n"

            extracted_data.append({
                "Course ID": row["course_id"],
                "Course Title": course_title,
                "Summary": summary,
                "Competencies": comp_str,
                "Modules": mod_str,
                "Learning Objectives": lo_str,
                "Assessment Framework": af_str,
                "Questions": questions_formatted,
                "Total Tokens": total_tokens,
                "Status": row["status"],
                "Generated At": row["generated_at"]
            })
            
        if not extracted_data:
            print("⚠️ No data to export.")
            return

        df = pd.DataFrame(extracted_data)
        output_file = os.path.join(OUTPUT_DIR, f"assessment_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        df.to_csv(output_file, index=False)
        print(f"✅ Exported to {output_file}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if conn:
            await conn.close()

if __name__ == "__main__":
    asyncio.run(export_filtered_fields())

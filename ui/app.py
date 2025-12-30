import streamlit as st
import requests
import time
import pandas as pd
import json
import os
from dotenv import load_dotenv

# Load local .env if present
load_dotenv()

# Read API_URL from environment or fallback
API_URL = os.getenv("API_URL", "http://localhost:8000")
# Append the versioned path if not already present
if not API_URL.endswith("/ai-assment-generation/api/v1"):
    API_URL = f"{API_URL.rstrip('/')}/ai-assment-generation/api/v1"

st.set_page_config(page_title="Assessment Generator v3.3", layout="wide")

st.title("Course Assessment Generator (Prompt v3.3)")

course_id = st.text_input("Enter Course ID", placeholder="do_1234567890")

if course_id:
    # Use active job ID from session if available (for polling), otherwise input ID (for initial check)
    current_job_id = st.session_state.get('active_job_id', course_id)
    
    # Check Status
    try:
        resp = requests.get(f"{API_URL}/status/{current_job_id}")
        
        if resp.status_code == 404:
            st.info("No assessment found for this course.")
            status = "NOT_FOUND"
        else:
            data = resp.json()
            status = data.get("status")
            st.write(f"**Current Status:** {status}")
            if status == "FAILED":
                st.error(f"Error: {data.get('error_message')}")

    except requests.exceptions.ConnectionError:
        st.error("Backend API is not running. Please start the FastAPI server.")
        st.stop()

    # Actions based on status
    if status == "NOT_FOUND" or status == "FAILED" or (status == "COMPLETED" and st.checkbox("Force Regenerate")):
        st.subheader("Generate Assessment")
        
        # Step 1: Core Config
        col1, col2, col3 = st.columns(3)
        with col1:
            assessment_type = st.selectbox("Assessment Type", ["practice", "final", "comprehensive"])
        with col2:
            difficulty = st.selectbox("Difficulty", ["beginner", "intermediate", "advanced"], index=1)
        with col3:
            language = st.selectbox(
                "Language Selection", 
                ["english", "hindi", "bengali", "gujarati", "kannada", "malayalam", "marathi", "tamil", "telugu", "odia", "punjabi", "assamese"]
            )

        # Step 2: Course Inputs
        if assessment_type == "comprehensive":
            course_ids_input = st.text_area("Target Course IDs (comma-separated)", value=course_id, placeholder="do_123, do_456, do_789")
        else:
            # Single course mode: Use the top-level input directly
            st.markdown(f"**Target Course:** `{course_id}`")
            course_ids_input = course_id

        total_questions = st.number_input("Total Questions (per type)", min_value=1, max_value=20, value=5)

        # Step 3: Question Config
        col_q1, col_q2 = st.columns(2)
        with col_q1:
            q_types = st.multiselect(
                "Question Types", 
                ["MCQ", "FTB", "MTF"], 
                default=["MCQ", "FTB", "MTF"]
            )
        with col_q2:
            time_limit = st.number_input("Time Limit (Minutes)", min_value=10, max_value=180, value=60, step=10)

        # Step 4: Advanced Config
        with st.expander("Advanced Configuration (Bloom's & Topics)", expanded=False):
            topic_names = st.text_input("Prioritize Topics (comma-separated)", placeholder="e.g. Budgeting, Risk Management, Python Basics")
            
            st.markdown("#### Bloom's Taxonomy Distribution (Must sum to 100%)")
            b_col1, b_col2, b_col3, b_col4, b_col5, b_col6 = st.columns(6)
            b_remember = b_col1.number_input("Remember %", value=20, min_value=0, max_value=100)
            b_understand = b_col2.number_input("Understand %", value=25, min_value=0, max_value=100)
            b_apply = b_col3.number_input("Apply %", value=25, min_value=0, max_value=100)
            b_analyze = b_col4.number_input("Analyze %", value=20, min_value=0, max_value=100)
            b_evaluate = b_col5.number_input("Evaluate %", value=10, min_value=0, max_value=100)
            b_create = b_col6.number_input("Create %", value=0, min_value=0, max_value=100)

            total_blooms = b_remember + b_understand + b_apply + b_analyze + b_evaluate + b_create
            if total_blooms != 100:
                st.warning(f"Total Bloom's Percentage: {total_blooms}%. It should be exactly 100%.")

        uploaded_files = st.file_uploader("Upload extra PDFs (Optional)", accept_multiple_files=True, type=['pdf'])
        additional_instructions = st.text_area("Additional Instructions (SME notes)", placeholder="e.g. Focus on Chapter 3, exclude technical jargon...")
        
        if st.button("Start Generation"):
            if total_blooms != 100:
                st.error("Cannot start: Bloom's Taxonomy distribution must equal 100%.")
                st.stop()
            
            if not q_types:
                st.error("Please select at least one Question Type.")
                st.stop()

            files = []
            if uploaded_files:
                for f in uploaded_files:
                    files.append(('files', (f.name, f.getvalue(), 'application/pdf')))
            
            # Construct Payload
            blooms_config = {
                "Remember": b_remember,
                "Understand": b_understand,
                "Apply": b_apply,
                "Analyze": b_analyze,
                "Evaluate": b_evaluate,
                "Create": b_create
            }
            
            q_types_str = ",".join(q_types)

            payload = {
                'course_ids': course_ids_input, 
                'force': 'true',
                'assessment_type': assessment_type,
                'difficulty': difficulty,
                'total_questions': total_questions,
                'question_types': q_types_str,
                'time_limit': time_limit,
                'topic_names': topic_names,
                'blooms_config': json.dumps(blooms_config),
                'additional_instructions': additional_instructions,
                'language': language
            }
            
            with st.spinner("Initiating job..."):
                r = requests.post(f"{API_URL}/generate", data=payload, files=files)
                if r.status_code == 200:
                    data = r.json()
                    new_job_id = data.get("job_id")
                    st.session_state['active_job_id'] = new_job_id
                    st.success(f"Job started! ID: {new_job_id}")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error(f"Failed to start job: {r.text}")

    elif status == "IN_PROGRESS" or status == "PENDING":
        st.info(f"Generation in progress for Job ID: {current_job_id}... Please wait.")
        progress_bar = st.progress(0)
        for i in range(100):
            time.sleep(0.1)
            progress_bar.progress(i + 1)
        
        time.sleep(2)
        st.rerun()

    elif status == "COMPLETED":
        st.success("Assessment Generated Successfully!")
        
        # Show details
        data = resp.json()
        
        st.subheader("Token Usage")
        token_usage = data.get("token_usage", {})
        if isinstance(token_usage, str):
            try:
                token_usage = json.loads(token_usage)
            except:
                pass
        st.json(token_usage, expanded=False)

        st.subheader("Assessment Results")
        assessment_data = data.get("assessment_data", {})
        if isinstance(assessment_data, str):
            try:
                assessment_data = json.loads(assessment_data)
            except:
                pass
        
        tab1, tab2 = st.tabs(["Blueprint", "Questions"])
        
        with tab1:
            blueprint = assessment_data.get("blueprint", {})
            st.info(f"**Audit Info:** Prompt {blueprint.get('prompt_version', 'N/A')} | API {blueprint.get('api_version', 'N/A')}")
            st.json(blueprint)
            
        with tab2:
            questions = assessment_data.get("questions", {})
            for q_type, q_list in questions.items():
                with st.expander(f"{q_type} ({len(q_list)} items)"):
                    for q in q_list:
                        st.markdown(f"**Q: {q.get('question_text', '')}**")
                        if q_type == "Multiple Choice Question":
                            for opt in q.get("options", []):
                                st.write(f"- {opt['text']}")
                            st.info(f"Answer: Option {q.get('correct_option_index')}")
                        elif q_type == "MTF Question":
                            for p in q.get("pairs", []):
                                st.write(f"- {p['left']} → {p['right']}")
                        else:
                            st.info(f"Answer: {q.get('correct_answer')}")
                        
                        # Explainability Section
                        reasoning = q.get('reasoning', {})
                        kcm = reasoning.get('competency_alignment', {}).get('kcm', {})
                        
                        rel_pct = q.get('relevance_percentage', 0)
                        st.write(f"**Relevance:** `{rel_pct}%` | **Bloom:** `{q.get('blooms_level', 'N/A')}`")
                        
                        with st.expander("View SME Alignment & Reasoning"):
                            st.markdown(f"**Learning Objective:** {reasoning.get('learning_objective_alignment')}")
                            st.markdown(f"**KCM Competency:** {kcm.get('competency_area')} → {kcm.get('competency_theme')} → {kcm.get('competency_sub_theme')}")
                            if reasoning.get('competency_alignment', {}).get('domain'):
                                st.markdown(f"**Domain Mapping:** {reasoning.get('competency_alignment', {}).get('domain')}")
                            st.markdown(f"**Bloom Justification:** {reasoning.get('blooms_level_justification')}")
                            st.markdown(f"**Difficulty Justification:** {reasoning.get('difficulty_justification')}")
                            st.markdown(f"**Rationale:** {reasoning.get('question_type_rationale')}")
                        st.divider()
        
        # Download
        st.subheader("Download Results")
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.link_button("Download JSON", f"{API_URL}/download_json/{current_job_id}")
        with col_dl2:
            st.link_button("Download CSV", f"{API_URL}/download_csv/{current_job_id}")

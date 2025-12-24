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

st.set_page_config(page_title="Assessment Generator v3.1", layout="wide")

st.title("Course Assessment Generator (Prompt v3.1)")

course_id = st.text_input("Enter Course ID", placeholder="do_1234567890")

if course_id:
    # Check Status
    try:
        resp = requests.get(f"{API_URL}/status/{course_id}")
        
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
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            assessment_type = st.selectbox("Assessment Type", ["practice", "final", "comprehensive"], index=1)
        with col2:
            difficulty = st.selectbox("Difficulty", ["Beginner", "Intermediate", "Advanced"], index=1)
        with col3:
            total_questions = st.number_input("Total Questions (per type)", min_value=1, max_value=20, value=5)
        with col4:
            language = st.selectbox(
                "Language Selection", 
                ["English", "Hindi", "Bengali", "Gujarati", "Kannada", "Malayalam", "Marathi", "Tamil", "Telugu", "Urdu"]
            )

        uploaded_files = st.file_uploader("Upload extra PDFs (Optional)", accept_multiple_files=True, type=['pdf'])
        additional_instructions = st.text_area("Additional Instructions (SME notes, exclusions, priorities)", placeholder="e.g. Focus on Chapter 3, exclude technical jargon...")
        
        if st.button("Start Generation"):
            files = []
            if uploaded_files:
                for f in uploaded_files:
                    files.append(('files', (f.name, f.getvalue(), 'application/pdf')))
            
            payload = {
                'course_id': course_id, 
                'force': 'true',
                'assessment_type': assessment_type,
                'difficulty': difficulty,
                'total_questions': total_questions,
                'additional_instructions': additional_instructions,
                'language': language
            }
            
            with st.spinner("Initiating job..."):
                r = requests.post(f"{API_URL}/generate", data=payload, files=files)
                if r.status_code == 200:
                    st.success("Job started!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Failed to start job: {r.text}")

    elif status == "IN_PROGRESS" or status == "PENDING":
        st.info("Generation in progress... Please wait.")
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
            st.link_button("Download JSON", f"{API_URL}/download_json/{course_id}")
        with col_dl2:
            st.link_button("Download CSV", f"{API_URL}/download/{course_id}")

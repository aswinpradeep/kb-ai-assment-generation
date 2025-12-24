import os
from pathlib import Path
from dotenv import load_dotenv

# Robustly find the .env file relative to this file's location
# Found in root
ROOT_DIR = Path(__file__).parent.parent.parent
ENV_PATH = ROOT_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

# API Configuration
KARMAYOGI_API_KEY = os.getenv("KARMAYOGI_API_KEY", "")
SEARCH_API_URL = "https://igotkarmayogi.gov.in/api/content/v1/search"
TRANSCODER_STATS_URL = "https://learning-ai.prod.karmayogibharat.net/api/kb-pipeline/v3/transcoder/stats"

# Database
DB_DSN = os.getenv("DB_DSN", "postgresql://myuser:mypassword@localhost:5432/karmayogi_db")

# Paths
# Store data in the root directory's interactive_courses_data folder
INTERACTIVE_COURSES_PATH = os.path.join(ROOT_DIR, "interactive_courses_data")

# Google GenAI
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
GOOGLE_LOCATION = os.getenv("GOOGLE_LOCATION", "us-central1")
GENAI_MODEL_NAME = os.getenv("GENAI_MODEL_NAME", "gemini-2.5-pro")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# Headers for Karmayogi API
API_HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'authorization': f'Bearer {KARMAYOGI_API_KEY}' if KARMAYOGI_API_KEY else '',
    'org': 'dopt',
    'rootorg': 'igot',
    'locale': 'en',
    # 'hostpath': 'portal.uat.karmayogibharat.net' # Optional based on JS
}

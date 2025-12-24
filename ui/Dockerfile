FROM python:3.11-slim

WORKDIR /app

# Copy requirement files first
COPY ui/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the UI code and any necessary root files (.env if needed)
COPY ui/ ./ui/

# Environment variable for the app
ENV API_URL=http://api:8000

EXPOSE 8501

ENTRYPOINT ["streamlit", "run", "ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]

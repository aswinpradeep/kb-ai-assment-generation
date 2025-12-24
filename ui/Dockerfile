FROM python:3.11-slim

WORKDIR /app

# Copy requirement files first
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy the UI code and any shared assets if needed
# Since this is a simple POC, we copy everything but we'll focus on ui/
COPY . .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]

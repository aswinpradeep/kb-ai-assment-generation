FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy local dependencies first to leverage Docker cache
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy the rest of the application
COPY . .

# Create directory for course data
RUN mkdir -p interactive_courses_data

# Expose port for FastAPI
EXPOSE 8000

ENV PYTHONPATH=/app/src

# Command to run both will be handled by docker-compose or a shell script
CMD ["uvicorn", "assessment.api:app", "--host", "0.0.0.0", "--port", "8000"]

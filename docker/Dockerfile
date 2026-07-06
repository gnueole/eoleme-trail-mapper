FROM python:3.11-slim-buster

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files and static assets
COPY garmin_course_injector.py .
COPY server.py .
COPY utils ./utils
COPY public ./public

# Expose the configured Traefik port
EXPOSE 3000

# Start FastAPI server on port 3000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "3000"]

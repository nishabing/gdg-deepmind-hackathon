FROM python:3.11-slim

# Avoid writing .pyc files and buffer output for live Cloud Run logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies first for efficient layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Cloud Run defaults to port 8080
EXPOSE 8080

# Launch the application (app.py binds to 0.0.0.0 and dynamically reads PORT)
CMD ["python", "app.py"]


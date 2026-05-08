# syntax=docker/dockerfile:1

# ── Build Stage ───────────────────────────────────────────────
FROM python:3.11-slim AS base

# Set working directory inside the container
WORKDIR /app

# Copy requirements first (better layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# ── Runtime Config ────────────────────────────────────────────
# Tell Flask to listen on all interfaces
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Document the port this app uses
EXPOSE 5000

# Start the Flask app
CMD ["python", "app.py"]
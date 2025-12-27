# ===== Dockerfile =====
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements first (for layer caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the service code
COPY . .

# Expose port
EXPOSE 5005

# Default environment variables
ENV FLASK_ENV=production \
    PYTHONUNBUFFERED=1

# Start the Flask server
CMD ["python", "server.py"]

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY sovereignguard/ ./sovereignguard/

# Create directories
RUN mkdir -p logs data

# Non-root user for security
RUN useradd -m -u 1000 sovereignguard
RUN chown -R sovereignguard:sovereignguard /app
USER sovereignguard

EXPOSE 8000 9090

CMD ["uvicorn", "sovereignguard.main:app", "--host", "0.0.0.0", "--port", "8000"]

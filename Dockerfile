FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    APP_DIR=/app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y curl bash build-essential && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR $APP_DIR

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Create a startup script
RUN echo '#!/bin/bash' > /start_service.sh && \
    echo "python ${APP_DIR}/service.py" >> /start_service.sh && \
    chmod +x /start_service.sh

# Run the service
CMD ["/start_service.sh"]

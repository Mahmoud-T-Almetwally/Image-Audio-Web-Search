# Use official Playwright image for included browsers & dependencies
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy 

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \ 
    && rm -rf /var/lib/apt/lists/*

# Install dependencies (Playwright image has Python/pip)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code, proto definitions, and the scrapy project
# Ensure generated files and copied gRPC files are included if needed within src
COPY ./src ./src

# Expose the gRPC port
EXPOSE 50052

# Command to run the service
CMD ["python", "-u", "-m", "src.server.main"]
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install official Ookla speedtest CLI
RUN curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | bash \
    && apt-get install -y speedtest

WORKDIR /app

# Copy and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure /data is writable (volume will be mounted here)
RUN mkdir -p /data && chmod 777 /data

CMD ["python", "main.py"]

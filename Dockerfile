FROM python:3.12-slim

# Install minimal system deps (ping + curl + ca-certificates for https)
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install official Ookla Speedtest CLI binary (direct download, no repo script)
# Latest stable as of 2025/2026 — check https://www.speedtest.net/apps/cli for updates
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then TARBALL="ookla-speedtest-1.2.0-linux-x86_64.tgz"; \
    elif [ "$ARCH" = "arm64" ]; then TARBALL="ookla-speedtest-1.2.0-linux-aarch64.tgz"; \
    else echo "Unsupported architecture: $ARCH" && exit 1; fi && \
    curl -L -o speedtest.tgz "https://install.speedtest.net/app/cli/${TARBALL}" && \
    tar xzf speedtest.tgz && \
    mv speedtest /usr/local/bin/speedtest && \
    chmod +x /usr/local/bin/speedtest && \
    rm speedtest.tgz && \
    # Accept license non-interactively on first run (required)
    speedtest --accept-license --accept-gdpr >/dev/null 2>&1 || true

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data && chmod 777 /data

CMD ["python", "main.py"]

FROM python:3.12-slim@sha256:37fc60d303cb9294d3718b5b48998a0210bb1c73611c1399ef5eb7964c0536e5
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/pallets/click.git /app \
 && git -C /app -c advice.detachedHead=false checkout --quiet cf19179e8e2fd54c601378cec9e0d21bb12b6fb1 \
 && git -C /app config user.email "agent@example.com" \
 && git -C /app config user.name "agent"
WORKDIR /app
RUN pip install --no-cache-dir pytest==8.4.1 \
 && pip install --no-cache-dir -e /app

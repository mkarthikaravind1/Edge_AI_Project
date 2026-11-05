# syntax=docker/dockerfile:1
# Edge inspection station image. Builds for linux/arm64 (Raspberry Pi) and linux/amd64 (laptop test).
#   docker buildx build --platform linux/arm64,linux/amd64 -f docker/Dockerfile -t edge-inspection:latest .
# Debian Bookworm = the same base as Raspberry Pi OS, so apt's picamera2/gpiozero work inside the container.
FROM debian:bookworm-slim

ARG TARGETARCH
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5 \
    EDGE_TARGET=pi \
    EDGE_ROOT=/app \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python3-pip ca-certificates curl gnupg libgl1 libglib2.0-0 tzdata \
    && rm -rf /var/lib/apt/lists/*

# Raspberry Pi camera stack (libcamera + Picamera2) and GPIO (gpiozero + lgpio) from the official Pi repository.
RUN if [ "$TARGETARCH" = "arm64" ]; then \
        curl -fsSL https://archive.raspberrypi.com/debian/raspberrypi.gpg.key \
            | gpg --dearmor -o /usr/share/keyrings/raspberrypi-archive-keyring.gpg && \
        echo "deb [signed-by=/usr/share/keyrings/raspberrypi-archive-keyring.gpg] http://archive.raspberrypi.com/debian/ bookworm main" \
            > /etc/apt/sources.list.d/raspi.list && \
        apt-get update && apt-get install -y --no-install-recommends \
            python3-picamera2 python3-libcamera python3-gpiozero python3-lgpio python3-smbus2 && \
        rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app
# --system-site-packages: the venv can see the apt-installed picamera2 / gpiozero
RUN python3 -m venv --system-site-packages /opt/venv
COPY requirements-pi.txt .
# BuildKit cache: downloaded wheels survive a failed/slow build, so a retry resumes instead of restarting
# the container has no screen: use the headless OpenCV build (the Pi's own venv keeps the GUI one for capture_rig.py)
RUN --mount=type=cache,target=/root/.cache/pip sed 's/^opencv-python>=/opencv-python-headless>=/' requirements-pi.txt > /tmp/req.txt \
    && pip install -r /tmp/req.txt

COPY pyproject.toml ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-deps .
COPY config ./config
COPY scripts ./scripts
COPY models/best_int8.tflite models/best_int8_full.tflite ./models/

EXPOSE 8000
CMD ["python", "-m", "edgevision.app"]

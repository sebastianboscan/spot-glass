# CORE I/O is a Jetson Xavier NX (arm64). The relay is CPU-only, so a plain
# Debian base avoids the size and JetPack pinning of nvidia/l4t-base.
FROM debian:bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Debian's prebuilt OpenCV; pip's opencv-python would build from source on arm64.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-flask \
        python3-opencv \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY spot_glass /app/spot_glass

RUN useradd --system --no-create-home --uid 10001 relay
USER relay

ENV LISTEN_HOST=0.0.0.0 \
    LISTEN_PORT=21000

EXPOSE 21000

CMD ["python3", "-m", "spot_glass", "thermal"]

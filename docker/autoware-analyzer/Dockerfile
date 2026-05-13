ARG AUTOWARE_IMAGE=ghcr.io/autowarefoundation/autoware:universe-jazzy-1.8.0
FROM ${AUTOWARE_IMAGE}

USER root

RUN apt-get update \
  && apt-get install -y --no-install-recommends python3-pip \
  && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --break-system-packages --no-cache-dir \
  "pydantic>=2,<3" \
  "typer>=0.12,<1" \
  "fastapi>=0.110,<1" \
  "uvicorn[standard]>=0.27,<1"

ENV PYTHONUNBUFFERED=1
WORKDIR /work

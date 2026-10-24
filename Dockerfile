FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV EVENT_MODEL_PATH=/app/models

# Install system libraries needed by OpenCV (cv2) and other native deps.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1
ENV UV_NO_INSTALLER_METADATA=1

# Install dependencies first (cache layer).
COPY pyproject.toml .
RUN uv pip install --system -r pyproject.toml

# Application code + model files (baked into the image for cloud deploy).
COPY . .

# Pre-download OCR weights and verify extraction model at build time.
RUN python scripts/check_setup.py

EXPOSE 8000

# One worker keeps memory flat; scale by running more containers.
CMD ["gunicorn", "gumastan.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1"]

FROM python:3.14-slim

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

# Application code (model files are downloaded below, not committed to git).
COPY . .

# Download the ONNX extraction model, pre-download OCR weights, and verify both.
RUN python scripts/download_models.py
RUN python scripts/check_setup.py

# Collect static files so WhiteNoise can serve them in production.
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Run the web workers and the db_worker command worker in one container.
# Dependencies are installed into the system interpreter above, so call it
# directly instead of `uv run` (which would create and sync a .venv).
CMD ["./entrypoint.sh"]

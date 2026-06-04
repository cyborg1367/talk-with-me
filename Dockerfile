# ── Build stage ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency manifest first — layer is cached until deps change
COPY pyproject.toml ./
COPY uv.lock* ./

# Install production dependencies into a virtualenv
RUN uv sync --no-dev --no-cache

# ── Runtime stage ─────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Copy the virtualenv from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

# HuggingFace Spaces runs containers as a non-root user (uid 1000)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# HuggingFace Spaces requires port 7860
EXPOSE 7860

# Activate the venv and start the server
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]

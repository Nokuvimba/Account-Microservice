# syntax=docker/dockerfile:1

# ---- Builder stage ----
FROM python:3.11-slim AS builder
WORKDIR /app

RUN pip install --upgrade pip wheel

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ---- Runtime stage ----
FROM python:3.11-slim AS runtime
WORKDIR /app

# Non-root user for security
RUN useradd -m appuser

# Install deps from prebuilt wheels
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy project code
COPY . .

USER appuser
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host=0.0.0.0", "--port=8000"]
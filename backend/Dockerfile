# backend/Dockerfile
# Build context is the repo root (see docker-compose.yml: context: .)
FROM python:3.11-slim

WORKDIR /app

# Install backend deps first for layer caching
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Backend source
COPY backend ./backend

# Pre-built frontend (run `npm run build` before docker build)
COPY frontend/dist ./frontend/dist

EXPOSE 8000
# backend.* is an importable package from /app
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

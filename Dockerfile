# Stage 1: build the React app
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: API + built frontend in one image
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
RUN useradd -m srk && mkdir -p /app/backend/uploads && chown -R srk /app
USER srk
EXPOSE 8000
CMD ["sh", "-c", "if [ \"$SEED_DEMO\" = \"1\" ]; then python seed.py; else python seed.py --base; fi; exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]

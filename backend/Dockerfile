FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend /app/backend
COPY scripts /app/scripts
COPY data /app/data
COPY saved_models /app/saved_models
COPY models /app/models
COPY ml /app/ml
COPY evaluation /app/evaluation
COPY reports /app/reports
RUN mkdir -p /app/data/processed/day9
EXPOSE 8000
CMD ["sh","-c","exec uvicorn backend.app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\""]

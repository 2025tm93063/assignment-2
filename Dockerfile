FROM python:3.11-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates/ templates/ 2>/dev/null || true

RUN useradd -m aceest
USER aceest

ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV DB_PATH=/tmp/aceest_fitness.db

EXPOSE 5000

CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5000"]

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY receiver ./receiver

ENV PYTHONPATH=/app

CMD ["uvicorn", "receiver.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

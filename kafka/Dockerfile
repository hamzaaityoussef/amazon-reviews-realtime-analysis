FROM python:3.9-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir kafka-python pymongo

CMD ["python", "producer.py"]

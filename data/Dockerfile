# ./data/Dockerfile
FROM python:3.9-slim

WORKDIR /app

# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt
# Install required packages

RUN pip install pymongo

COPY . .

CMD ["python", "mongo_loader.py"]
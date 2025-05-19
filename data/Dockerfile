# ./data/Dockerfile
FROM python:3.9-slim

WORKDIR /app



RUN pip install pymongo

COPY . .

CMD ["python", "mongo_loader.py"]
FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY web/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY web/ .

EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0"]
FROM python:3.9-slim

WORKDIR /app

# Update package lists and install Java (required for PySpark)
RUN apt-get update && \
    apt-get install -y --no-install-recommends openjdk-17-jre-headless && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir pymongo pyspark kafka-python textblob numpy

# Copy the model files
COPY model/logistic_regression_model /app/model/logistic_regression_model

# Copy the consumer code and preprocess script
COPY kafka/consumer.py .
COPY utils /app/utils

# Set environment variable for Java (ensures PySpark finds Java 17)
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH=$PATH:$JAVA_HOME/bin

CMD ["python", "consumer.py"]
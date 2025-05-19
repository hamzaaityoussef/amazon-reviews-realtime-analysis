FROM python:3.9-slim

WORKDIR /app

# Update package lists and install Java (required for PySpark)
RUN apt-get update && \
    apt-get install -y --no-install-recommends openjdk-17-jre-headless procps && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir pymongo==4.6.3 pyspark==3.5.3 kafka-python==2.0.2 textblob==0.18.0 numpy==1.26.4 pandas==2.2.2 spacy
RUN python -m spacy download en_core_web_sm



# Copy the consumer code and preprocess script
COPY model/ ./model/
COPY kafka/consumer.py .
COPY utils/ ./utils/

# Set environment variable for Java (ensures PySpark finds Java 17)
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH=$PATH:$JAVA_HOME/bin


ENV SPARK_WORKER_MEMORY=1g
ENV SPARK_DRIVER_MEMORY=1g

CMD ["python", "consumer.py"]
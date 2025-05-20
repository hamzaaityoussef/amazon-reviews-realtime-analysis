# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Update package lists and install Java (required for PySpark) and build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    procps \
    build-essential \
    python3-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    pymongo==4.6.3 \
    pyspark==3.5.3 \
    kafka-python==2.0.2 \
    textblob==0.18.0 \
    numpy==1.26.4 \
    pandas==2.2.2 \
    spacy==3.7.2
RUN python -m spacy download en_core_web_sm

# Copy the model files and application code
COPY model/ ./model/
COPY kafka/consumer.py .
COPY utils/ ./utils/

# Validate model files
RUN if [ ! -f ./model/logistic_regression_model/metadata/part-00000 ] || [ ! -f ./model/idf_model/metadata/part-00000 ]; then \
    echo "Model metadata file missing" && exit 1; \
    fi

# Set environment variable for Java (ensures PySpark finds Java 17)
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH=$PATH:$JAVA_HOME/bin

# Set Spark memory configuration
ENV SPARK_WORKER_MEMORY=2g
ENV SPARK_DRIVER_MEMORY=2g

# Run the application
CMD ["python", "consumer.py"]
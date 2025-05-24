# 📊 Real-Time Amazon Reviews Sentiment Analysis

This project is a real-time system for processing and analyzing Amazon product reviews to determine their sentiment (positive, neutral, negative) using Kafka, Spark, MongoDB, Docker, Machine Learning, and advanced visualization tools.

## 🧱 Architecture

- **Kafka** for real-time streaming of customer reviews
- **Spark (PySpark + MLlib)** for distributed processing and sentiment analysis using machine learning models
- **MongoDB** for storing predictions and processed data
- **Flask** for the web API and real-time dashboard (using Chart.js)
- **Power BI** for advanced business intelligence and offline analytics
- **Docker** for containerizing all services and ensuring easy deployment

**Data Flow:**
1. Amazon reviews are streamed into **Kafka**.
2. **Spark Streaming** processes the data, applies ML models (sentiment analysis), and stores results in **MongoDB**.
3. **Flask** web app fetches data from MongoDB and visualizes it in real-time using **Chart.js**.
4. **Power BI** connects to MongoDB for advanced analytics and business dashboards.

## 🚀 Getting Started

> Use `docker-compose.yml` to launch the entire stack.

```bash
docker-compose up --build
```

## 📁 Project Structure

- `kafka/` – Producer and consumer scripts for Kafka
- `web/` – Flask web server and dashboard (Chart.js)
- `data/` – Datasets and data loader scripts
- `model/` – Saved ML models (Logistic Regression, TF-IDF, etc.)
- `utils/` – Preprocessing and utility scripts
- `notebooks/` – Jupyter notebooks for model training and experimentation
- `PowerBI/` – power BI visualisation

## 📊 Visualization

- **Chart.js**: Real-time web dashboard for monitoring sentiment trends
- **Power BI**: Advanced business intelligence dashboards connected to MongoDB

## 👥 Team

- Hamza ait youssef
- Amina Louazir
- Diae Khayati

## 🛠️ Technologies

- Python, Docker, Apache Kafka, Apache Spark, MongoDB, Flask, Chart.js, Power BI

## 📌 Features

- Real-time ingestion and processing of Amazon reviews
- Automated sentiment analysis using machine learning
- Scalable, containerized microservices architecture
- Interactive dashboards for both real-time and offline analytics


N.B : btw you may have probleme when cloning the project in the part of models (maybe corrupted) , if that's the case try to unzip the zip models in the folder \Zipped_Models into model folder and it will works ان شاء الله , good luck

# 📊 Analyse en Temps Réel des Avis Amazon

Ce projet a pour but de créer un système de traitement en temps réel des commentaires Amazon pour déterminer leur polarité (positif, neutre, négatif), à l’aide de Kafka, Spark, MongoDB, Docker et d’un modèle de machine learning.

## 🧱 Architecture

- **Kafka** pour le streaming des avis clients
- **Spark (PySpark)** pour le traitement et l'entraînement des modèles
- **MongoDB** pour le stockage des prédictions
- **Flask** pour l'API Web (mode online)
- **Dashboard offline** pour l'analyse globale
- **Docker** pour conteneuriser l’ensemble

## 🚀 Lancement du projet

> À venir : docker-compose.yml

## 📁 Structure du projet

- `kafka/` – scripts de publication/consommation
- `spark/` – code de traitement ML
- `api/` – serveur Flask
- `dashboard/` – visualisations offline
- `data/` – données téléchargées de Kaggle
- `model/` – modèle ML sauvegardé

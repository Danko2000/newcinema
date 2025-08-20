# src/microservices/events/config.py
import os

class Settings:
    """
    Класс для хранения настроек сервиса событий.
    Загружает значения из переменных окружения.
    """
    def __init__(self):
        self.port: int = int(os.getenv("PORT", 8082))
        # Kafka брокеры, например: kafka:9092
        self.kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        # Имя топика для событий
        self.kafka_topic: str = os.getenv("KAFKA_TOPIC", "cinema-abyss-events")

# Экземпляр настроек для использования в приложении
settings = Settings()
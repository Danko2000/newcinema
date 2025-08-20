# src/microservices/proxy/config.py
import os

class Settings:
    """
    Класс для хранения настроек прокси-сервиса.
    Загружает значения из переменных окружения.
    """
    def __init__(self):
        self.port: int = int(os.getenv("PORT", 8000))
        self.monolith_url: str = os.getenv("MONOLITH_URL", "http://localhost:8080")
        self.movies_service_url: str = os.getenv("MOVIES_SERVICE_URL", "http://localhost:8081")
        self.events_service_url: str = os.getenv("EVENTS_SERVICE_URL", "http://localhost:8082")
        
        # Логика постепенной миграции
        self.gradual_migration: bool = os.getenv("GRADUAL_MIGRATION", "false").lower() == "true"
        self.movies_migration_percent: int = int(os.getenv("MOVIES_MIGRATION_PERCENT", 0))

# Экземпляр настроек для использования в приложении
settings = Settings()
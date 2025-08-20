# src/microservices/events/main.py
import uuid
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
from config import settings
from kafka_client import kafka_client

# Настройка логгирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Создание экземпляра FastAPI приложения
app = FastAPI(title="Events Service", version="1.0.0")

# Модели Pydantic для валидации входных данных
class MovieEvent(BaseModel):
    movie_id: int
    title: str
    action: str # viewed, rated, added
    user_id: int | None = None
    rating: float | None = None
    genres: list[str] | None = None
    description: str | None = None

class UserEvent(BaseModel):
    user_id: int
    action: str # registered, logged_in
    timestamp: str # ISO 8601 format
    username: str | None = None
    email: str | None = None

class PaymentEvent(BaseModel):
    payment_id: int
    user_id: int
    amount: float
    status: str # completed, failed
    timestamp: str # ISO 8601 format
    method_type: str | None = None

class EventResponse(BaseModel):
    status: str
    partition: int
    offset: int
    # event: dict # Можно вернуть полное событие, если нужно

# Фоновая задача для потребления событий
async def consume_events_background():
    """Фоновая задача для непрерывного потребления событий из Kafka."""
    try:
        async for event in kafka_client.consume_events():
            # Обработка события
            # В данном случае просто логируем, но здесь можно добавить любую логику
            logger.info(f"Обработано событие: {event}")
            # Пример: запись в БД, отправка в другой сервис и т.д.
    except Exception as e:
        logger.error(f"Ошибка в фоновой задаче потребления событий: {e}")

@app.on_event("startup")
async def startup_event():
    """
    Событие при запуске приложения.
    Инициализирует Kafka producer и consumer, запускает фоновую задачу.
    """
    logger.info("Запуск Events Service...")
    try:
        # Инициализация Kafka producer
        kafka_client.init_producer()
        
        # Инициализация Kafka consumer
        kafka_client.init_consumer()
        
        # Запуск фоновой задачи для потребления событий
        # asyncio.create_task позволяет запустить задачу в фоне
        # asyncio.create_task(consume_events_background())
        kafka_client.start_consuming()
        
        logger.info("Events Service успешно запущен")
    except Exception as e:
        logger.error(f"Ошибка при запуске Events Service: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """
    Событие при завершении работы.
    Останавливает Kafka producer и consumer.
    """
    logger.info("Остановка Events Service...")
    kafka_client.stop_producer()
    kafka_client.stop_consumer()
    logger.info("Events Service остановлен")

@app.get("/api/events/health")
async def health_check():
    """
    Эндпоинт для проверки состояния микросервиса событий.
    
    Returns:
        dict: Статус сервиса.
    """
    return {"status": True}

def _create_event_payload(event_type: str, event_data: BaseModel) -> dict:
    """
    Создает общий формат события для отправки в Kafka.
    
    Args:
        event_type (str): Тип события (movie, user, payment).
        event_data (BaseModel): Данные события.
        
    Returns:
        dict: Словарь с полным описанием события.
    """
    return {
        "id": str(uuid.uuid4()), # Уникальный ID события
        "type": event_type,
        "timestamp": datetime.utcnow().isoformat() + "Z", # Время в UTC
        "payload": event_data.dict(exclude_unset=True) # Только установленные поля
    }

@app.post("/api/events/movie", status_code=201)
async def create_movie_event(event: MovieEvent):
    """
    Создание события фильма.
    
    Args:
        event (MovieEvent): Данные события фильма.
        
    Returns:
        EventResponse: Ответ с результатом создания события.
    """
    logger.info(f"Получен запрос на создание события фильма: {event}")
    try:
        # Создаем общий формат события
        event_payload = _create_event_payload("movie", event)
        
        # Отправляем событие в Kafka
        topic, partition, offset = kafka_client.send_event(event_payload)
        
        return {
            "status": "success",
            "partition": partition,
            "offset": offset,
            # "event": event_payload # Можно вернуть, если нужно
        }
    except Exception as e:
        logger.error(f"Ошибка при создании события фильма: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/api/events/user", status_code=201)
async def create_user_event(event: UserEvent):
    """
    Создание события пользователя.
    
    Args:
        event (UserEvent): Данные события пользователя.
        
    Returns:
        EventResponse: Ответ с результатом создания события.
    """
    logger.info(f"Получен запрос на создание события пользователя: {event}")
    try:
        # Создаем общий формат события
        event_payload = _create_event_payload("user", event)
        
        # Отправляем событие в Kafka
        topic, partition, offset = kafka_client.send_event(event_payload)
        
        return {
            "status": "success",
            "partition": partition,
            "offset": offset,
            # "event": event_payload
        }
    except Exception as e:
        logger.error(f"Ошибка при создании события пользователя: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/api/events/payment", status_code=201)
async def create_payment_event(event: PaymentEvent):
    """
    Создание события платежа.
    
    Args:
        event (PaymentEvent): Данные события платежа.
        
    Returns:
        EventResponse: Ответ с результатом создания события.
    """
    logger.info(f"Получен запрос на создание события платежа: {event}")
    try:
        # Создаем общий формат события
        event_payload = _create_event_payload("payment", event)
        
        # Отправляем событие в Kafka
        topic, partition, offset = kafka_client.send_event(event_payload)
        
        return {
            "status": "success",
            "partition": partition,
            "offset": offset,
            # "event": event_payload
        }
    except Exception as e:
        logger.error(f"Ошибка при создании события платежа: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# Для запуска с помощью `python main.py`
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=True, log_level="info")
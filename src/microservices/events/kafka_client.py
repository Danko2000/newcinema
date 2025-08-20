# src/microservices/events/kafka_client.py
import json
import logging
from confluent_kafka import Producer, Consumer, KafkaException, KafkaError
from config import settings
import asyncio
import threading

# Настройка логгирования
logger = logging.getLogger(__name__)

class KafkaClient:
    """
    Класс для управления Kafka producer и consumer с использованием confluent-kafka.
    """
    def __init__(self):
        self.producer_conf = {
            'bootstrap.servers': settings.kafka_bootstrap_servers,
            'client.id': 'cinema-abyss-events-producer'
        }
        self.consumer_conf = {
            'bootstrap.servers': settings.kafka_bootstrap_servers,
            'group.id': 'events-service-group',
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False, # Отключаем автокоммит для лучшего контроля
             'client.id': 'cinema-abyss-events-consumer'
        }
        self.producer: Producer = None
        self.consumer: Consumer = None
        self.is_consumer_running = False
        self._consumer_thread = None

    def init_producer(self):
        """Инициализация Kafka Producer."""
        try:
            self.producer = Producer(self.producer_conf)
            logger.info("Kafka Producer (confluent-kafka) инициализирован")
        except Exception as e:
            logger.error(f"Ошибка при инициализации Kafka Producer: {e}")
            raise

    def init_consumer(self):
        """Инициализация Kafka Consumer."""
        try:
            self.consumer = Consumer(self.consumer_conf)
            self.consumer.subscribe([settings.kafka_topic])
            logger.info("Kafka Consumer (confluent-kafka) инициализирован и подписан на топик")
            self.is_consumer_running = True
        except Exception as e:
            logger.error(f"Ошибка при инициализации Kafka Consumer: {e}")
            raise

    def _delivery_report(self, err, msg):
        """Callback вызывается после доставки сообщения или при ошибке."""
        if err is not None:
            logger.error(f'Сообщение доставлено с ошибкой: {err}')
        else:
            logger.info(f'Сообщение доставлено в топик {msg.topic()} [{msg.partition()}] @ {msg.offset()}')

    def send_event(self, event_data: dict) -> tuple[str, int, int]:
        """
        Отправка события в Kafka.
        
        Args:
            event_data (dict): Данные события.
            
        Returns:
            tuple[str, int, int]: Кортеж (topic, partition, offset) отправленного сообщения.
                                  offset будет -1, так как confluent-kafka не возвращает его немедленно.
        """
        if not self.producer:
            raise RuntimeError("Kafka Producer не инициализирован")
            
        try:
            # Сериализуем данные в JSON
            serialized_value = json.dumps(event_data, ensure_ascii=True)
            
            # Отправляем сообщение
            # poll(0) нужен для обработки событий доставки
            self.producer.produce(settings.kafka_topic, value=serialized_value, callback=self._delivery_report)
            # Ждем завершения отправки (не обязательно, но хорошо для гарантии)
            self.producer.poll(0) 
            
            logger.info(f"Событие отправлено в Kafka: {event_data}")
            # confluent-kafka не предоставляет partition/offset немедленно в простом вызове
            # В реальном приложении можно использовать callback или отдельный poll для получения статуса
            return (settings.kafka_topic, -1, -1) # Заглушки
        except KafkaException as e:
            logger.error(f"Ошибка Kafka при отправке события: {e}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке события: {e}")
            raise

    def _consume_loop(self):
        """Внутренний метод для непрерывного потребления сообщений."""
        try:
            while self.is_consumer_running:
                msg = self.consumer.poll(timeout=1.0) # Таймаут 1 секунда

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        # Конец партиции, продолжаем
                        logger.debug('Достигнут конец партиции {0} [{1}] при offset {2}'.format(
                                     msg.topic(), msg.partition(), msg.offset()))
                    elif msg.error():
                        logger.error(f"Ошибка Kafka: {msg.error()}")
                        raise KafkaException(msg.error())
                else:
                    # Обрабатываем сообщение
                    try:
                        # Десериализуем значение
                        event_data = json.loads(msg.value().decode('utf-8'))
                        logger.info(f"Получено событие из Kafka: {event_data}")
                        # Здесь можно добавить логику обработки события
                        # Например, запись в БД, отправка уведомлений и т.д.
                        # Пока просто логируем
                        
                        # Подтверждаем сообщение (commit)
                        # Это упрощенный вариант, в production лучше группами
                        self.consumer.commit(message=msg, asynchronous=False)
                    except json.JSONDecodeError as e:
                        logger.error(f"Ошибка декодирования JSON из сообщения: {e}")
                        # Можно отправить в DLQ (Dead Letter Queue) или просто закоммитить, чтобы не зацикливалось
                        self.consumer.commit(message=msg, asynchronous=False)
                    except Exception as e:
                        logger.error(f"Ошибка обработки сообщения: {e}")
                        # В зависимости от логики, можно не коммитить, чтобы повторить обработку
                        # Или отправить в DLQ. Пока коммитим, чтобы продолжить.
                        self.consumer.commit(message=msg, asynchronous=False)
                        
        except Exception as e:
            logger.error(f"Критическая ошибка в цикле потребления: {e}")
        finally:
            logger.info("Цикл потребления остановлен")

    def start_consuming(self):
        """Запуск фонового потока для потребления событий."""
        if not self.consumer:
            raise RuntimeError("Kafka Consumer не инициализирован")

        if self._consumer_thread is None or not self._consumer_thread.is_alive():
            self.is_consumer_running = True
            self._consumer_thread = threading.Thread(target=self._consume_loop, daemon=True)
            self._consumer_thread.start()
            logger.info("Фоновый поток потребления Kafka запущен")

    def stop_producer(self):
        """Остановка Kafka Producer."""
        if self.producer:
            # Ждем завершения всех отправок
            self.producer.flush()
            logger.info("Kafka Producer остановлен")

    def stop_consumer(self):
        """Остановка Kafka Consumer."""
        self.is_consumer_running = False
        if self._consumer_thread and self._consumer_thread.is_alive():
            # Ждем завершения потока
            self._consumer_thread.join(timeout=5)
            logger.info("Фоновый поток потребления Kafka остановлен")
        if self.consumer:
            self.consumer.close()
            logger.info("Kafka Consumer остановлен")

# Глобальный экземпляр клиента
kafka_client = KafkaClient()

# src/microservices/proxy/main.py
import random
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
import asyncio
from config import settings

# Создание экземпляра FastAPI приложения
app = FastAPI(title="Proxy Service (API Gateway)", version="1.0.0")

# Создаем асинхронные HTTP клиенты для каждого сервиса
# Используем httpx.AsyncClient для асинхронных запросов
clients = {
    "monolith": httpx.AsyncClient(base_url=settings.monolith_url, timeout=30.0),
    "movies": httpx.AsyncClient(base_url=settings.movies_service_url, timeout=30.0),
    # "events": httpx.AsyncClient(base_url=settings.events_service_url, timeout=30.0), # Если понадобится
}

@app.on_event("startup")
async def startup_event():
    """Событие при запуске приложения: можно инициализировать ресурсы."""
    # Клиенты уже созданы при импорте, но можно добавить логику проверки подключения
    pass

@app.on_event("shutdown")
async def shutdown_event():
    """Событие при завершении работы: закрываем HTTP клиенты."""
    for client in clients.values():
        await client.aclose()

def should_route_to_microservice() -> bool:
    """
    Определяет, должен ли запрос быть направлен в микросервис
    на основе процента миграции.
    """
    if not settings.gradual_migration:
        return False
    return random.randint(1, 100) <= settings.movies_migration_percent

async def proxy_request(client: httpx.AsyncClient, path: str, request: Request) -> Response:
    """
    Асинхронно перенаправляет запрос в указанный клиент (сервис).
    
    Args:
        client: httpx.AsyncClient для целевого сервиса.
        path: Путь запроса.
        request: Исходный FastAPI Request.
        
    Returns:
        Response: Ответ от целевого сервиса.
    """
    # Формируем URL для запроса к целевому сервису
    url = httpx.URL(path=path, query=request.url.query.encode("utf-8"))
    
    # Подготавливаем параметры для httpx
    rp_req = client.build_request(
        method=request.method,
        url=url,
        headers=request.headers.raw,
        content=await request.body(),
    )
    
    # Выполняем запрос
    rp_resp = await client.send(rp_req, stream=True)
    
    # Возвращаем потоковый ответ
    return StreamingResponse(
        rp_resp.aiter_raw(),
        status_code=rp_resp.status_code,
        headers=rp_resp.headers,
        background=rp_resp.aclose, # Закрываем соединение в фоне
    )

@app.api_route("/api/movies{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def handle_movies(request: Request, path: str = ""):
    """
    Обрабатывает все запросы к /api/movies, реализуя логику постепенного перехода.
    
    Args:
        request: Исходный запрос.
        path: Дополнительный путь (например, /123).
        
    Returns:
        Response: Ответ от монолита или микросервиса.
    """
    full_path = f"/api/movies{path}"
    
    if settings.gradual_migration and should_route_to_microservice():
        # Перенаправление на микросервис Movies
        print(f"Routing {full_path} to movies-service")
        return await proxy_request(clients["movies"], full_path, request)
    else:
        # Перенаправление на монолит
        print(f"Routing {full_path} to monolith")
        return await proxy_request(clients["monolith"], full_path, request)

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_to_monolith(request: Request, path: str):
    """
    Универсальный обработчик для перенаправления всех остальных запросов в монолит.
    Исключает маршрут /api/movies, который обрабатывается отдельно.
    
    Args:
        request: Исходный запрос.
        path: Путь запроса.
        
    Returns:
        Response: Ответ от монолита.
    """
    # Исключаем маршрут /api/movies, чтобы не было конфликта
    if path.startswith("api/movies"):
        # Это не должно произойти из-за более специфичного маршрута выше,
        # но на всякий случай
        return await proxy_request(clients["monolith"], f"/{path}", request)
        
    print(f"Routing /{path} to monolith")
    return await proxy_request(clients["monolith"], f"/{path}", request)

@app.get("/health")
async def health_check():
    """
    Эндпоинт для проверки состояния прокси-сервиса.
    
    Returns:
        dict: Статус сервиса.
    """
    return {"status": "ok", "service": "proxy-service", "version": "1.0.0"}

# Для запуска с помощью `python main.py`
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=True, log_level="info")

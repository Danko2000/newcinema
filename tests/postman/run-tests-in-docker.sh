#!/bin/bash

# Проверка, запущен ли скрипт в Windows (Git Bash) или Unix-системе
# для корректного монтирования тома
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
  # Для Windows Git Bash предполагаем, что текущая директория находится на диске C:
  # И получаем путь в формате Windows для монтирования
  # Это может потребовать корректировки в зависимости от вашей ОС и настроек WSL/Docker Desktop
  # Простой способ - использовать pwd и заменить /c/ на //c (или соответствующий формат для Docker Desktop)
  # Но самый надежный способ - указать путь вручную или использовать абсолютный путь Windows
  # Например, если проект находится в C:\newcinema\tests\postman
  # HOST_PWD="//c/newcinema/tests/postman"
  HOST_PWD=$(pwd -W 2>/dev/null) # Попробуем получить путь Windows через pwd -W
  if [ -z "$HOST_PWD" ]; then
     # Если pwd -W не сработал, попробуем преобразовать
     HOST_PWD=$(pwd | sed 's/^\/\([a-zA-Z]\)\//\/\/\1\//')
  fi
else
  # Для Linux/macOS используем обычный pwd
  HOST_PWD=$(pwd)
fi

echo "Using host path for volume mount: $HOST_PWD"

# Определяем аргументы окружения и папки, переданные скрипту
# Это позволяет передавать флаги типа --folder "Movies Microservice" в этот скрипт
# которые затем будут переданы внутрь контейнера в newman
NEWMAN_ARGS=""
while [[ $# -gt 0 ]]; do
  case $1 in
    -e|--environment)
      ENV_ARG="$2"
      shift 2
      ;;
    -f|--folder)
      FOLDER_ARG="$2"
      shift 2
      ;;
    -r|--reporters)
      REPORTERS_ARG="$2"
      shift 2
      ;;
    -b|--bail)
      BAIL_ARG="--bail"
      shift
      ;;
    -t|--timeout)
      TIMEOUT_ARG="--timeout-request $2"
      shift 2
      ;;
    *)
      # Если переданы другие аргументы, добавляем их как есть
      NEWMAN_ARGS="$NEWMAN_ARGS $1"
      shift
      ;;
  esac
done

# Формируем команду Newman внутри контейнера
NEWMAN_CMD="npx newman run CinemaAbyss.postman_collection.json"
if [ -n "$ENV_ARG" ]; then
  NEWMAN_CMD="$NEWMAN_CMD -e $ENV_ARG.environment.json"
fi
if [ -n "$FOLDER_ARG" ]; then
  NEWMAN_CMD="$NEWMAN_CMD --folder \"$FOLDER_ARG\""
fi
if [ -n "$REPORTERS_ARG" ]; then
  NEWMAN_CMD="$NEWMAN_CMD -r $REPORTERS_ARG"
fi
if [ -n "$BAIL_ARG" ]; then
  NEWMAN_CMD="$NEWMAN_CMD $BAIL_ARG"
fi
if [ -n "$TIMEOUT_ARG" ]; then
  NEWMAN_CMD="$NEWMAN_CMD $TIMEOUT_ARG"
fi
# Добавляем любые другие аргументы
NEWMAN_CMD="$NEWMAN_CMD $NEWMAN_ARGS"

echo "Running Newman command inside Docker: $NEWMAN_CMD"

# Запуск контейнера Docker
# --rm: Удалить контейнер после завершения
# --network cinemaabyss-network: Подключиться к сети Docker Compose
# -v "$HOST_PWD:/etc/newman": Примонтировать текущую директорию в /etc/newman внутри контейнера
# -w /etc/newman: Установить рабочую директорию внутри контейнера
# node:18-alpine: Использовать образ Node.js 18 на Alpine Linux (легкий)
# sh -c "...": Выполнить команду внутри контейнера
# npm install newman: Установить Newman внутри контейнера
# && npm install newman-reporter-htmlextra: Установить htmlextra reporter (если используется)
# && $NEWMAN_CMD: Выполнить сформированную команду Newman
docker run --rm \
  --network cinemaabyss-network \
  -v "$HOST_PWD:/etc/newman" \
  -w /etc/newman \
  node:18-alpine \
  sh -c "npm install newman newman-reporter-htmlextra newman-reporter-junit && $NEWMAN_CMD"

# Проверяем код возврата команды docker run
EXIT_CODE=$?
echo "Docker run exited with code: $EXIT_CODE"
exit $EXIT_CODE
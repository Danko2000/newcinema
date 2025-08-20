// run-tests-docker.js
const { spawn } = require('child_process');
const path = require('path');
// Убедитесь, что yargs установлен в tests/postman: npm install yargs
const yargs = require('yargs/yargs');
const { hideBin } = require('yargs/helpers');

/**
 * Этот скрипт запускает тесты Postman Newman внутри Docker-контейнера.
 * Это необходимо для того, чтобы Newman мог разрешать имена Docker-сервисов
 * (например, 'monolith', 'movies-service') в их IP-адреса внутри сети Docker.
 */

// Парсим аргументы командной строки
const argv = yargs(hideBin(process.argv))
  .option('environment', {
    alias: 'e',
    description: 'Environment to run tests against (e.g., docker, local)',
    type: 'string',
    default: 'docker' // По умолчанию используем 'docker' окружение
  })
  .option('collection', {
    alias: 'c',
    description: 'Collection to run',
    type: 'string',
    default: 'CinemaAbyss'
  })
  .option('folder', {
    alias: 'f',
    description: 'Specific folder in the collection to run',
    type: 'string'
  })
  .option('reporters', {
    alias: 'r',
    description: 'Reporters to use (comma-separated)',
    type: 'string',
    default: 'cli,htmlextra,junit'
  })
  .option('bail', {
    alias: 'b',
    description: 'Stop on first error',
    type: 'boolean',
    default: false
  })
  .option('timeout', {
    alias: 't',
    description: 'Request timeout in ms',
    type: 'number',
    default: 10000
  })
  .help()
  .alias('help', 'h')
  .argv;

// Формируем аргументы для команды Newman внутри Docker
let newmanArgs = ['run', `${argv.collection}.postman_collection.json`];

if (argv.environment) {
  newmanArgs.push('-e', `${argv.environment}.environment.json`);
}
if (argv.folder) {
  newmanArgs.push('--folder', argv.folder);
}
if (argv.reporters) {
  newmanArgs.push('-r', argv.reporters);
}
if (argv.bail) {
  newmanArgs.push('--bail');
}
if (argv.timeout) {
  newmanArgs.push('--timeout-request', argv.timeout.toString());
}
// Добавляем небольшую задержку, как в оригинальном скрипте
newmanArgs.push('--delay-request', '100');

console.log('Preparing to run Newman inside Docker with args:', newmanArgs);

// Формируем команду для docker run
// Используем process.cwd() для получения текущей директории
let hostPwd = process.cwd();
console.log(`Original host path for volume mount: ${hostPwd}`);

// Обработка пути для Windows (Docker Desktop)
let volumeMount;
if (process.platform === "win32") {
    console.log("Detected Windows platform. Attempting to format path for Docker Desktop...");
    
    // Преобразуем обратные слэши Windows в прямые слэши
    hostPwd = hostPwd.replace(/\\/g, '/');
    
    // Формат для Docker Desktop на Windows: путь_хоста:путь_в_контейнере
    // Без экранирования двоеточия и без кавычек вокруг всей строки
    volumeMount = `${hostPwd}:/etc/newman`;
    console.log(`Using volume mount: ${volumeMount}`);
    
} else {
    // Для Unix-систем используем стандартный формат
    volumeMount = `${hostPwd}:/etc/newman`;
    console.log(`Using Unix path for volume mount: ${volumeMount}`);
}

// Команда, которая будет выполнена внутри контейнера
// Она устанавливает необходимые пакеты и запускает Newman
// Убран несуществующий пакет newman-reporter-junit
const containerCommand = `
  npm install newman newman-reporter-htmlextra &&
  npx newman ${newmanArgs.map(arg => `'${arg}'`).join(' ')}
`;

const dockerArgs = [
  'run', '--rm', // Удалить контейнер после завершения
  '--network', 'cinemaabyss-network', // Подключиться к сети Docker Compose
  '-v', volumeMount, // Примонтировать текущую директорию (с учетом форматирования для Windows)
  '-w', '/etc/newman', // Установить рабочую директорию внутри контейнера
  'node:18-alpine', // Использовать легкий образ Node.js
  'sh', '-c', // Выполнить команду через shell
  containerCommand
];

console.log('Executing Docker command: docker', ...dockerArgs); // Используем spread operator для чистого вывода

// Запускаем процесс docker
const dockerProcess = spawn('docker', dockerArgs, { stdio: 'inherit' });

// Обрабатываем завершение процесса docker
dockerProcess.on('close', (code) => {
  console.log(`Docker process exited with code ${code}`);
  process.exit(code);
});

// Обрабатываем ошибки запуска процесса docker
dockerProcess.on('error', (error) => {
  console.error('Failed to start Docker process:', error.message);
  // Добавим подсказку, если Docker не найден
  if (error.code === 'ENOENT') {
      console.error('Please make sure Docker is installed and running.');
  }
  process.exit(1);
});
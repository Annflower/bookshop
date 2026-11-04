# Запуск и настройка

## Требования

- **Python 3.12+** (проверено на 3.14.7)
- **MySQL 5.5+** (используется существующая БД `bookshop_full`, utf8mb4)
- Менеджер пакетов `pip`

## Переменные окружения (`.env`)

Скопируйте `.env.example` в `.env` и укажите значения.

| Переменная | Обязательна | Описание |
|------------|-------------|----------|
| `DATABASE_URL` | да | Строка подключения MySQL. Формат: `mysql+pymysql://<user>:<pass>@<host>:<port>/<dbname>?charset=utf8mb4` |
| `JWT_SECRET` | да | Секрет для подписи токенов. Сгенерируйте длинную случайную строку |

> ⚠️ **`API_TOKEN` больше не используется.** Раньше аналитика защищалась API-токеном, теперь — входом пользователя с ролью `admin`. Если в `.env` остался `API_TOKEN` — удалите его.

## Локальный запуск (без Docker)

```bash
# 1. venv + зависимости
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

# 2. .env
copy .env.example .env        # затем укажите DATABASE_URL и JWT_SECRET

# 3. запуск
uvicorn app.main:app --reload --port 8000
# открой http://localhost:8000
```

> Если нужен перезапуск после правок backend — без `--reload` перезапустите uvicorn вручную (убить старый процесс и запустить заново).

## Деплой «в облако» (Railway / Render / Fly.io)

1. Залейте репозиторий на GitHub.
2. Создайте сервис из `bookshop_py/Dockerfile`.
3. Укажите `DATABASE_URL` и `JWT_SECRET` в переменных окружения платформы.
4. Платформа поднимет приложение по адресу вида `https://<app>.onrender.com`.

## docker-compose (локально с БД)

```bash
docker compose up -d --build
```

Compose поднимает `app` (порт 8000) и `db` (MySQL 5.7, `bookshop_full`), инициализируя БД из `../bookshop_full/database.sql` (относительно `bookshop_py/`).

> ℹ️ Если запускаете `docker compose` из директории `bookshop_py/`, соседняя папка `bookshop_full` должна существовать — из неё монтируется дамп `database.sql` как init-скрипт.

## Подключение существующей БД

- Локально: `DATABASE_URL=mysql+pymysql://root:@localhost:3306/bookshop_full?charset=utf8mb4`
- Облако: дайте доступ к БД по host/port/user/pass, создайте БД `bookshop_full` и импортируйте `bookshop_full/database.sql`. Структура (`users.password_hash`, `users.role`, `users.city`, `orders.city`, таблицы `favorites`/`reviews`/`complaints`) должна соответствовать схеме проекта — при отсутствии полей/таблиц выполните миграции из [`database.md`](database.md).

## Рабочая структура файлов

```
bookshop_py/
├── app/
│   ├── main.py        # FastAPI: маршруты, auth, отдача frontend
│   ├── db.py          # подключение SQLAlchemy + helpers
│   ├── auth.py        # хеш паролей (PBKDF2) + подписанные токены
│   ├── services.py    # бизнес-логика: товары, заказ, избранное, жалобы, аналитика
│   └── schemas.py     # Pydantic-схемы
├── frontend/
│   ├── index.html     # каталог, корзина, чекаут, аналитика
│   ├── style.css
│   └── app.js         # вызовы API (fetch + Bearer)
├── db/                # SQL-миграции (favorites.sql)
├── docs/              # вся документация (см. корневой README.md)
├── requirements.txt   # pip-зависимости (ОБЯЗАТЕЛЬНО в корне: Dockerfile копирует его)
├── Dockerfile         # образ (должен быть в корне контекста сборки)
├── docker-compose.yml # app + MySQL (должен быть в корне проекта)
├── .env.example
└── README.md          # точка входа (единственный README в проекте)
```

## Безопасность

- Все SQL-запросы — параметризованные (SQLAlchemy Core + `text`), без конкатенации строк.
- Пароли хранятся в виде PBKDF2-HMAC-SHA256 (`iter$salt_hex$digest_hex`), сравнение в постоянном времени.
- Токен подписывается HMAC-SHA256 (`JWT_SECRET`); секреты — в `.env`, не в коде.
- Аналитика и админ-жалобы закрыты проверкой `role == 'admin'`.
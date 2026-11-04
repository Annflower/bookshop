# 📚 bookshop_py

**FastAPI-бэкенд** книжного магазина + аналитики. Переиспользует существующую БД `bookshop_full` (та же схема, что и в PHP-версии) и предлагает **современный REST API + фронтенд на HTML/CSS/JS**. Это «вариант 3»: полный переезд backend на Python; PHP-проект (`bookshop_full/`) не тронут.

```
Браузер (HTML+JS)  ←→  FastAPI (Python)  ←→  MySQL (bookshop_full)
   frontend/             app/main.py           уже существующая схема
```

- **Backend:** FastAPI + SQLAlchemy Core (PyMySQL), Pydantic-валидация.
- **Frontend:** простой `HTML+CSS+JS` (`frontend/`), ходит в API по JSON.
- **БД:** та же `bookshop_full` (не пересоздаётся, только читается/пишется), дополнена для аналитики (см. [`docs/database.md`](docs/database.md)).

---

## Быстрый старт

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env        # указать DATABASE_URL и JWT_SECRET
uvicorn app.main:app --reload --port 8000
```

Открой `http://localhost:8000`. Swagger UI: `http://localhost:8000/docs`.

---

## Эндпоинты (сводка)

| Метод | Путь | Auth | Описание |
|-------|------|------|----------|
| GET | `/api/products` | нет | Список товаров (`?category=`, `?q=`, `?limit=`, `?offset=`) |
| GET | `/api/products/{id}` | нет | Карточка товара |
| GET | `/api/categories` | нет | Категории |
| POST | `/api/orders` | опц. | Создать заказ (в транзакции; `city?`) |
| POST | `/api/ai/search` | нет | ИИ-поиск по смыслу (`query`, `limit`) |
| GET | `/api/favorites` | да | Список избранного |
| POST | `/api/favorites` | да | Добавить в избранное (`product_id`) |
| DELETE | `/api/favorites/{id}` | да | Убрать из избранного |
| GET | `/api/favorites/{id}` | да | Проверить, в избранном ли |
| POST | `/api/complaints` | опц. | Подать жалобу о проблеме с книгой |
| GET | `/api/complaints` | **admin** | Список жалоб |
| PATCH | `/api/complaints/{id}` | **admin** | Сменить статус жалобы |
| POST | `/api/auth/register` | нет | Регистрация |
| POST | `/api/auth/login` | нет | Вход |
| GET | `/api/auth/me` | да | Текущий пользователь |
| GET | `/api/analytics/order-facts` | **admin** | Факты заказов |
| GET | `/api/analytics/product-sales` | **admin** | Продажи по товарам |
| GET | `/api/analytics/daily-revenue` | **admin** | Выручка по дням |
| GET | `/api/analytics/event-log` | **admin** | Журнал событий |
| GET | `/api/analytics/kpi` | **admin** | Сводные KPI |
| GET | `/api/analytics/cities` | **admin** | Топ городов |
| GET | `/api/analytics/reviews` | **admin** | Отзывы |
| GET | `/api/health` | нет | Проверка БД |

**Auth:** заголовок `Authorization: Bearer <token>`. Роль `admin` даёт доступ к аналитике и обработке жалоб. Все подробности — [`docs/api.md`](docs/api.md).

---

## Чем отличается от PHP-версии

| Аспект | PHP `bookshop_full` | Python `bookshop_py` |
|--------|---------------------|----------------------|
| Backend | PHP 5.3+ (PDO) | **Python 3.12+ (FastAPI)** |
| БД | MySQL `bookshop_full` | **та же MySQL `bookshop_full`** |
| API | `api/*.php` | **FastAPI-эндпоинты** |
| Frontend | серверный HTML | **HTML+JS (fetch → JSON)** |
| Авторизация | `admins` (bcrypt) + API-токен | **единый вход по ролям (`users.role`)** |
| Аналитика | витрины + экспорт | **витрины + KPI + города + отзывы** |

Подробно: [`docs/architecture.md`](docs/architecture.md), [`docs/auth-roles.md`](docs/auth-roles.md).

---

## Структура проекта

```
bookshop_py/
├── app/                       # FastAPI-приложение
│   ├── main.py                # маршруты, авторизация, отдача frontend
│   ├── db.py                  # подключение SQLAlchemy + helpers
│   ├── auth.py                # пароли (PBKDF2) + подписанные токены
│   ├── services.py            # бизнес-логика: товары, заказ, избранное, жалобы, аналитика
│   └── schemas.py             # Pydantic-схемы
├── frontend/                  # SPA (HTML + CSS + JS)
│   ├── index.html             # каталог, корзина, чекаут, аналитика
│   ├── style.css
│   └── app.js                 # вызовы API (fetch + Bearer)
├── db/                        # SQL-миграции
│   └── favorites.sql          # CREATE TABLE favorites
├── docs/                      # документация (см. раздел ниже)
├── requirements.txt           # pip-зависимости (нужен в корне — Dockerfile делает COPY)
├── Dockerfile                 # образ (в корне — контекст сборки)
├── docker-compose.yml         # app + MySQL (в корне — docker compose up)
├── .env.example               # шаблон переменных окружения
└── README.md                  # этот файл — единственная точка входа
```

---

## Документация

| Документ | Содержание |
|----------|------------|
| [`docs/requirements/requirements.md`](docs/requirements/requirements.md) | **Функциональные (FR)** и **нефункциональные (NFR)** требования, роли, критерии приёмки |
| [`docs/requirements/user-stories.md`](docs/requirements/user-stories.md) | User stories по ролям + матрица покрытия US→FR |
| [`docs/requirements/use-cases.md`](docs/requirements/use-cases.md) | Варианты использования (UC) с потоками и API |
| [`docs/requirements/bpmn.md`](docs/requirements/bpmn.md) | **BPMN-диаграммы** ключевых процессов (Mermaid) |
| [`docs/architecture.md`](docs/architecture.md) | Архитектура: слои, компоненты, потоки данных |
| [`docs/api.md`](docs/api.md) | Все REST-эндпоинты, тела запросов, коды статусов |
| [`docs/database-schema.md`](docs/database-schema.md) | ERD + полный словарь данных (таблицы, поля, связи) |
| [`docs/database.md`](docs/database.md) | Миграции проекта, демо-данные, владелец-админ |
| [`docs/auth-roles.md`](docs/auth-roles.md) | Вход, роли `user`/`admin`, как зайти в аналитику |
| [`docs/analytics.md`](docs/analytics.md) | KPI, вкладки, гео, отзывы, выгрузка для DS |
| [`docs/setup.md`](docs/setup.md) | Запуск, `.env`, Docker, деплой, безопасность |
| [`docs/roadmap.md`](docs/roadmap.md) | Что сделано / в планах (фазы, приоритеты) |

**С чего начать:** впервые в проекте → [`docs/architecture.md`](docs/architecture.md) + [`docs/database-schema.md`](docs/database-schema.md); запустить → [`docs/setup.md`](docs/setup.md); аналитику → [`docs/analytics.md`](docs/analytics.md) + [`docs/auth-roles.md`](docs/auth-roles.md); API → [`docs/api.md`](docs/api.md).

---

## Ключевые особенности

- **Аналитика — через вход администратора.** Нет отдельного входа админа: зайдите обычным «Войти» аккаунтом с ролью `admin`. Демо-владелец: `owner@bookverse.ru` / `owner123456`. Подробно — [`docs/auth-roles.md`](docs/auth-roles.md).
- **Данные за ~полгода** для аналитики как в реальном проекте (города, отзывы, повторные покупки) — [`docs/analytics.md`](docs/analytics.md), [`docs/database.md`](docs/database.md).
- **Избранное и жалобы** — публичные (создание жалобы) и авторизованные (избранное, админ-жалобы) фичи.
- **ИИ-поиск** по смыслу (без внешних моделей): нормализация фразы + синонимы тем + idf-ранжирование.

## Миграции БД

Проект дополняет базовую схему `bookshop_full`:
- `users.password_hash`, `users.role`, `users.city`, `orders.city`, таблицы `favorites`, `reviews`, `complaints`.

Отдельный SQL-файл — [`db/favorites.sql`](db/favorites.sql) (идемпотентно):
```bash
mysql -u root -p < db/favorites.sql
```
Полные DDL всех миграций — [`docs/database.md`](docs/database.md); описание схемы — [`docs/database-schema.md`](docs/database-schema.md).

---

## Аналитика и DS

Витрины `v_order_facts`, `v_product_sales`, `v_daily_revenue`, `v_event_log` доступны через защищённые эндпоинты. Из Python (нужны `pandas` + `pymysql`):

```python
import pandas as pd, pymysql
conn = pymysql.connect(host='localhost', user='root', password='',
                       db='bookshop_full', charset='utf8mb4')
order_facts = pd.read_sql("SELECT * FROM v_order_facts", conn)
daily = pd.read_sql("SELECT * FROM v_daily_revenue", conn)
conn.close()
```

**Или готовый скрипт** (без pandas, только PyMySQL):
```bash
.venv\Scripts\python.exe analysis\report.py   # выгрузит CSV + напечатает KPI
```
Подробно — [`docs/analytics.md`](docs/analytics.md).

---

## Деплой «в облако» (Docker)

Вариант A — **Railway / Render / Fly.io**:
1. Залейте репозиторий на GitHub.
2. Создайте сервис из `Dockerfile`.
3. Укажите `DATABASE_URL` и `JWT_SECRET` в переменных окружения платформы.
4. Платформа поднимет приложение по адресу вида `https://<app>.<platform>.com`.

Вариант B — **docker-compose** (локально с БД):
```bash
docker compose up -d --build
```
Compose поднимает `app` (порт 8000) и `db` (MySQL 5.7), инициализируя БД из `../bookshop_full/database.sql`. Подробности — [`docs/setup.md`](docs/setup.md).

---

## Безопасность

- Все SQL-запросы — параметризованные (SQLAlchemy Core), без конкатенации.
- Пароли — PBKDF2-HMAC-SHA256 (сравнение в постоянном времени).
- Токены — самоподписанные HMAC-SHA256 (`JWT_SECRET`), секреты в `.env`.
- Аналитика и админ-жалобы — только для `role == 'admin'`.

## Быстрые факты

- **Стек:** FastAPI + SQLAlchemy Core + PyMySQL, SPA на HTML/CSS/JS.
- **БД:** `bookshop_full` (MySQL, utf8mb4), дополнена `role`, `city`, `favorites`, `reviews`, `complaints`.
- **Аналитика:** только для `role = 'admin'` (единый вход, без отдельного API-токена).
- **Swagger:** `http://localhost:8000/docs`.

## Что дальше

- Пагинация каталога/заказов.
- Дашборд с графиками (Chart.js), экспорт в Parquet, пайплайн в DuckDB/pandas.
- Тесты (pytest) + CI.

Полный план — [`docs/roadmap.md`](docs/roadmap.md).
# Схема БД и данные

`bookshop_py` использует **существующую** БД `bookshop_full` (схема из PHP-версии). Проект её не пересоздаёт — только читает и пишет. Дамп схемы + витрин + демо-данных: `bookshop_full/database.sql`.

> 📖 Полный ERD и словарь данных (типы, ключи, nullable, связи по каждой таблице) — в [`database-schema.md`](database-schema.md). Здесь — краткая сводка, миграции проекта и демо-данные.

## Базы данных на сервере

На этом MySQL (localhost) есть 7 баз:

| База | Кодировка | Русское название | Зачем |
|------|-----------|------------------|-------|
| **`bookshop_full`** | utf8mb4 | **Книжный магазин (основная)** | **Рабочая БД проекта** — сюда пишет `bookshop_py`. Все данные сайта. |
| `bookshop` | utf8 | **Книжный магазин (старая)** | Старая/резервная версия без `role`, `city`, `favorites`, `reviews`, `complaints`. **Проектом не используется.** |
| `language_courses` | utf8 | **Курсы языков** | Отдельная база (не книжный магазин). К проекту не относится. |
| `information_schema` | utf8 | **Система: схемы** | Служебная БД MySQL (метаданные о БД/таблицах). Не трогаем. |
| `mysql` | utf8 | **Система: пользователи** | Служебная (учётки, права). Не трогаем. |
| `performance_schema` | utf8 | **Система: производительность** | Служебная (мониторинг производительности). Не трогаем. |
| `phpmyadmin` | utf8_bin | **Система: phpMyAdmin** | Служебная для панели phpMyAdmin. Не трогаем. |

> **Как смотреть:** удобнее всего через **phpMyAdmin** (обычно `http://localhost/phpmyadmin` → слева выбрать `bookshop_full` → слева таблицы) или через **Swagger** (`http://localhost:8000/docs`). Для серьёзной работы — клиент **DBeaver** / **HeidiSQL**.

## Таблицы `bookshop_full` (русские названия и назначение)

| Таблица | Русское название | Зачем нужна |
|---------|------------------|-------------|
| `users` | **Пользователи** | Покупатели и владельцы; хранит `role` (`user`/`admin`), `password_hash`, `city` |
| `products` | **Товары (книги)** | Каталог: название, автор, цена `base_price`, остаток `in_stock`, категория |
| `categories` | **Категории** | Разделы каталога (художественная, учебная, детская, фантастика…) |
| `orders` | **Заказы** | Каждый заказ: кто, город `city`, сумма `total_amount`, статус |
| `order_items` | **Состав заказа** | Позиции внутри заказа: книга, количество, цена на момент покупки (`price` — effective price) |
| `order_status_history` | **История статусов заказа** | Лог смены статусов: что было → что стало, кем и когда |
| `favorites` | **Избранное** | Книги, сохранённые пользователем в избранное (добавлена проектом) |
| `reviews` | **Отзывы** | Оценки и тексты отзывов на книги (добавлена проектом) |
| `complaints` | **Жалобы** | Заявки о проблемах: брак, не та книга и т.п. (добавлена проектом) |
| `event_log` | **Журнал событий** | Продуктовая аналитика/воронка: кто что делал (просмотр, корзина, заказ) |
| `admins` | **Администраторы (старая)** | Легаси из PHP-версии; **не используется** `bookshop_py` — там вход через `users.role='admin'` |

### Витрины (views) — готовые отчёты

| View | Русское название | Зачем |
|------|------------------|-------|
| `v_order_facts` | **Факты заказов** | 1 строка = 1 заказ (покупатель, дата, сумма) |
| `v_product_sales` | **Продажи по товарам** | 1 строка = товар в заказе (цена, кол-во, сумма) |
| `v_daily_revenue` | **Выручка по дням** | Выручка / заказы / средний чек за день |
| `v_event_log` | **Журнал событий** | События с датой для воронки |

## Схема (таблицы)

`bookshop_full` содержит, в частности:
- `users` — покупатели/админы; **добавлены** поля `password_hash`, `role`, `city`
- `products`, `categories` — товары и категории
- `orders`, `order_items`, `order_status_history` — заказы, состав, история статусов (**добавлено** `orders.city`)
- `favorites` — избранное; **добавлена таблица** (DDL: `db/favorites.sql`, идемпотентный `CREATE TABLE IF NOT EXISTS`)
- `reviews` — **добавлена таблица** отзывов
- `complaints` — **добавлена таблица** жалоб/брака
- `event_log` — журнал событий (воронка аналитики)
- витрины `v_order_facts`, `v_product_sales`, `v_daily_revenue`, `v_event_log`

### Миграции, внесённые этим проектом

```sql
-- users: пароль + роль + город
ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NULL;
ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user';
ALTER TABLE users ADD COLUMN city VARCHAR(191) NULL;

-- orders: город
ALTER TABLE orders ADD COLUMN city VARCHAR(191) NULL;

-- отзывы
CREATE TABLE reviews (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  product_id INT NOT NULL,
  user_id INT NOT NULL,
  rating INT NOT NULL,
  text TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_reviews_product (product_id),
  KEY idx_reviews_user (user_id),
  CONSTRAINT fk_reviews_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  CONSTRAINT fk_reviews_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- жалобы / брак
CREATE TABLE complaints (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  product_id INT NOT NULL,
  user_id INT NULL,
  name VARCHAR(255) NOT NULL,
  email VARCHAR(191) NOT NULL,
  phone VARCHAR(50) NULL,
  issue_type VARCHAR(50) NOT NULL DEFAULT 'damage',
  description TEXT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'new',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NULL DEFAULT NULL,
  KEY idx_complaints_product (product_id),
  KEY idx_complaints_user (user_id),
  KEY idx_complaints_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

`favorites` (таблица):
```sql
CREATE TABLE IF NOT EXISTS favorites (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  product_id INT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_favorites_user_product (user_id, product_id),
  KEY idx_favorites_product (product_id),
  CONSTRAINT fk_favorites_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_favorites_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

## Демо-данные (за ~полгода)

Для аналитики в БД добавлены реалистичные данные примерно за период **06.05.2026 — 02.11.2026**:

- **52 клиента** из **~22 городов** (Москва, Санкт-Петербург, Ростов-на-Дону, Казань, Уфа, Новосибирск, Екатеринбург и др.)
- **~185 заказов** по статусам: `completed` ~79, `shipped` ~37, `processing` ~38, `new` ~18, `cancelled` ~13
- **Повторные покупатели** (до 10 заказов у некоторых)
- **89 отзывов** (средняя оценка ~4.5)
- **16 жалоб** (с событиями в `event_log`)
- **56 избранных**
- **180 событий** (`view_catalog`, `search`, `add_to_cart`, `order_created` и т.д.)

Сидинг идемпотентный: очищает заказы/отзывы/жалобы/избранное/клиентов (кроме admin) и генерирует заново.

## Владелец (admin)

Демо-владелец создан как обычный пользователь с ролью `admin` (пароль PBKDF2, совместим с `app/auth.py`):
- email `owner@bookverse.ru`, пароль `owner123456`

> ⚠️ Старый механизм `admins` (bcrypt из PHP) **не используется** — он несовместим с Python-хешированием. Вход в аналитику — через `users` с `role='admin'`.

## Изменение/наполнение данных

Схема и данные управляются идемпотентными скриптами (под `bookshop_py/_seed.py` и подобными). После завершения разовых работ такие временные `_*.py`-скрипты удаляются, чтобы проект оставался чистым.
# Аналитика

Аналитика в `bookshop_py` доступна **только пользователю с ролью `admin`** и открывается через ссылку «📊 Аналитика» в навбаре. Страница использует Bearer-токен авторизованного пользователя (не API-токен).

## Что показывает дашборд

**KPI-карточки** (живые цифры из БД): всего заказов, выручка, уникальные клиенты, средний чек, количество городов, количество отзывов, открытых жалоб.

**Вкладки:**

| Вкладка | Источник (эндпоинт) | Что показывает |
|---------|---------------------|----------------|
| Заказы | `/api/analytics/order-facts` | Список заказов: покупатель, дата, сумма, статус |
| Товары / Продажи | `/api/analytics/product-sales` | Продажи по товарам: цена, количество, сумма, категория |
| Выручка | `/api/analytics/daily-revenue` | Выручка/заказы/средний чек по дням |
| События | `/api/analytics/event-log` | Журнал событий (воронка) |
| Города | `/api/analytics/cities` | Топ городов: заказы, клиенты, выручка |
| Отзывы | `/api/analytics/reviews` | Оценки пользователей с названием книги |
| Жалобы | `/api/complaints` | Заявки о проблемах + смена статуса |

## Сводные показатели (KPI)

Эндпоинт `/api/analytics/kpi` возвращает словарь:
- `orders_total` — число заказов (кроме `cancelled`)
- `customers_total` — уникальных пользователей в заказах
- `revenue_total` — сумма `orders.total_amount` (кроме `cancelled`)
- `avg_order` — средний чек
- `reviews_total` — число отзывов
- `complaints_open` — жалобы со статусом `new` / `processing`
- `cities_total` — количество уникальных городов из `orders.city`

## Гео (города)

В `orders` есть поле `city`. Оно заполняется: при создании заказа из `OrderCreateIn.city`, а также обновляется из профиля пользователя при авторизованном заказе. На аналитике города группируются по `orders.city` (исключая пустые и отменённые).

## Отзывы (reviews)

Таблица `reviews` хранит `product_id`, `user_id`, `rating`, `text`, `created_at`. На аналитике соединяется с `users` (имя) и `products` (название книги) — отображается **название книги** и **имя пользователя**.

## Данные для DS / выгрузки

Витрины `v_order_facts`, `v_product_sales`, `v_daily_revenue`, `v_event_log` (в БД `bookshop_full`) доступны через защищённые эндпоинты. Из Python:
```python
import pandas as pd, pymysql
conn = pymysql.connect(host='localhost', user='root', password='',
                       db='bookshop_full', charset='utf8mb4')
order_facts = pd.read_sql("SELECT * FROM v_order_facts", conn)
daily = pd.read_sql("SELECT * FROM v_daily_revenue", conn)
conn.close()
```

Для этого нужны `pandas` и `pymysql`.

## Готовый скрипт аналитики

В проекте есть скрипт, который **сам подключается к БД** и выгружает все отчёты в CSV + печатает сводку. Не требует pandas (использует только PyMySQL).

```bash
# из корня bookshop_py
.venv\Scripts\python.exe analysis\report.py
```

Он создаёт папку `analysis/out/` с файлами:
- `order_facts.csv` — факты заказов
- `product_sales.csv` — продажи по товарам
- `daily_revenue.csv` — выручка по дням
- `event_log.csv` — журнал событий
- `reviews.csv` — отзывы
- `complaints.csv` — жалобы

И печатает KPI-сводку (заказы, выручка, клиенты, средний чек, отзывы, открытые жалобы, города).

> Файлы пишутся в кодировке UTF-8 с BOM (`utf-8-sig`) — открываются корректно в Excel.

## Демо-данные

БД `bookshop_full` наполнена реалистичными данными примерно за **полгода**: 52 клиента из ~22 городов, ~185 заказов (completed/shipped/processing/new/cancelled), отзывы, повторные покупки, журнал событий, жалобы. Это позволяет сразу строить метрики «как в реальном проекте» (см. `docs/database.md`).
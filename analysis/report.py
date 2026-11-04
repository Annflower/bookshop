# -*- coding: utf-8 -*-
"""Скрипт аналитики bookshop_py.

Подключается к БД bookshop_full (URL берётся из .env или дефолт root:@localhost),
собирает готовые отчёты и выгружает их в CSV-файлы в папку analysis/out/.
Не требует pandas — только PyMySQL (уже в venv) или sqlalchemy.

Запуск (из корня bookshop_py):
    .venv\\Scripts\\python.exe analysis\\report.py
"""

import csv
import os
from decimal import Decimal
from datetime import datetime, date

# --- Подключение к БД ---
# Пытаемся прочитать DATABASE_URL из .env; иначе дефолт (как в app/db.py).
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:@localhost:3306/bookshop_full?charset=utf8mb4")

# Простой парсер DSN "mysql+pymysql://user:pass@host:port/db?params"
def _parse_dsn(dsn):
    dsn = dsn.replace("mysql+pymysql://", "").replace("mysql://", "")
    rest, _, query = dsn.partition("?")
    cred, _, hostpart = rest.rpartition("@")
    user, _, password = cred.partition(":")
    # hostpart = "host:port/dbname"
    hostport, _, dbname = hostpart.partition("/")
    if ":" in hostport:
        host, _, port = hostport.partition(":")
    else:
        host, port = hostport, "3306"
    return {
        "host": host or "localhost",
        "port": int(port or 3306),
        "user": user or "root",
        "password": password,
        "db": dbname or "bookshop_full",
        "charset": "utf8mb4",
    }


import pymysql


def connect():
    cfg = _parse_dsn(DATABASE_URL)
    return pymysql.connect(
        host=cfg["host"], port=cfg["port"], user=cfg["user"],
        password=cfg["password"], database=cfg["db"], charset=cfg["charset"],
    )


# --- Вспомогательное ---
def norm(v):
    """Приводит значения к csv-стайлу (Decimal/date -> str)."""
    if v is None:
        return ""
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def dump(conn, sql, path, columns):
    conn.ping()
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(columns)
        for r in rows:
            w.writerow([norm(x) for x in r])
    return len(rows)


def query_one(conn, sql):
    conn.ping()
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()


# --- Отчёты ---
OUT = os.path.join(os.path.dirname(__file__), "out")


def main():
    conn = connect()
    print("Подключено к", conn.get_server_info())
    print("=" * 72)
    print("Выгружаю отчёты в", OUT)
    print("=" * 72)

    # 1. Факты заказов
    n = dump(conn, "SELECT * FROM v_order_facts ORDER BY order_date DESC",
             os.path.join(OUT, "order_facts.csv"),
             ["order_id", "status", "customer_email", "order_date",
              "order_date_day", "order_year", "order_month", "total_amount", "items_count"])
    print(f"[1/6] order_facts.csv — {n} строк")

    # 2. Продажи по товарам
    n = dump(conn, "SELECT * FROM v_product_sales ORDER BY order_date_day DESC, line_total DESC",
             os.path.join(OUT, "product_sales.csv"),
             ["order_id", "product_id", "product_name", "category_id", "category_name",
              "quantity", "unit_price", "line_total", "order_status", "order_date_day"])
    print(f"[2/6] product_sales.csv — {n} строк")

    # 3. Выручка по дням
    n = dump(conn, "SELECT * FROM v_daily_revenue ORDER BY revenue_date DESC",
             os.path.join(OUT, "daily_revenue.csv"),
             ["revenue_date", "orders_count", "customers_count", "revenue", "avg_order_value"])
    print(f"[3/6] daily_revenue.csv — {n} строк")

    # 4. Журнал событий
    n = dump(conn, "SELECT * FROM v_event_log ORDER BY created_at DESC",
             os.path.join(OUT, "event_log.csv"),
             ["id", "event_type", "session_id", "user_id", "product_id", "order_id",
              "value", "created_at", "event_date_day"])
    print(f"[4/6] event_log.csv — {n} строк")

    # 5. Отзывы
    n = dump(conn,
             "SELECT r.id, r.product_id, r.user_id, r.rating, r.text, r.created_at, "
             "u.name AS user_name, p.name AS product_name "
             "FROM reviews r JOIN users u ON r.user_id=u.id JOIN products p ON r.product_id=p.id "
             "ORDER BY r.created_at DESC",
             os.path.join(OUT, "reviews.csv"),
             ["id", "product_id", "user_id", "rating", "text", "created_at", "user_name", "product_name"])
    print(f"[5/7] reviews.csv — {n} строк")

    # 6. Жалобы
    n = dump(conn,
             "SELECT c.id, c.product_id, c.name, c.email, c.issue_type, c.description, c.status, c.created_at "
             "FROM complaints c ORDER BY c.created_at DESC",
             os.path.join(OUT, "complaints.csv"),
             ["id", "product_id", "name", "email", "issue_type", "description", "status", "created_at"])
    print(f"[6/7] complaints.csv — {n} строк")

    # 7. Заказы с городом (для гео-аналитики)
    n = dump(conn,
             "SELECT o.id AS order_id, o.user_id, o.city, o.total_amount AS amount, o.status, o.created_at "
             "FROM orders o ORDER BY o.created_at DESC",
             os.path.join(OUT, "orders.csv"),
             ["order_id", "user_id", "city", "amount", "status", "created_at"])
    print(f"[7/7] orders.csv — {n} строк")

    # --- Сводка KPI ---
    print("\n" + "=" * 72)
    print("СВОДКА (KPI)")
    print("=" * 72)
    row = query_one(conn,
        "SELECT COUNT(*) AS orders, COALESCE(SUM(total_amount),0) AS revenue, "
        "COUNT(DISTINCT user_id) AS customers, "
        "(SELECT COUNT(*) FROM reviews) AS reviews, "
        "(SELECT COUNT(*) FROM complaints WHERE status IN ('new','processing')) AS open_complaints "
        "FROM orders WHERE status <> 'cancelled'")
    print(f"  Заказов (кроме отменённых): {row[0]}")
    print(f"  Выручка:                    {row[1]:,.2f} ₽")
    print(f"  Уникальных клиентов:        {row[2]}")
    print(f"  Отзывов:                    {row[3]}")
    print(f"  Открытых жалоб:             {row[4]}")

    avg = query_one(conn,
        "SELECT COALESCE(AVG(total_amount),0) FROM orders WHERE status <> 'cancelled'")
    print(f"  Средний чек:                {avg[0]:,.2f} ₽")

    cities = query_one(conn,
        "SELECT COUNT(DISTINCT city) FROM orders WHERE city IS NOT NULL AND city <> '' AND status <> 'cancelled'")
    print(f"  Городов в заказах:          {cities[0]}")

    conn.close()
    print("\nГотово. Файлы в папке:", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
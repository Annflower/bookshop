"""Подключение к БД и единый доступ к соединению (SQLAlchemy).

Переиспользует уже существующую БД `bookshop_full` (MySQL, utf8mb4),
созданную из `bookshop_full/database.sql`. Все запросы — через SQLAlchemy Core
с параметризацией (безопасно) и JSON-сериализацией (Decimal/Date/DateTime).
"""

import os
from decimal import Decimal
from datetime import date, datetime

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:@localhost:3306/bookshop_full?charset=utf8mb4",
)

# pool_pre_ping для устойчивости подключения (в т.ч. в облаке)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

def row_to_dict(row):
    """Преобразует строку SQLAlchemy в dict: Decimal->float, дата->iso.

    Это нужно для корректной JSON-сериализации (Decimal/date не сериализуются
    стандартным json.dumps).
    """
    if row is None:
        return None
    if isinstance(row, dict):
        data = dict(row)
    else:
        data = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)

    for k, v in list(data.items()):
        if isinstance(v, Decimal):
            data[k] = float(v)
        elif isinstance(v, datetime):
            data[k] = v.isoformat(sep=" ")
        elif isinstance(v, date):
            data[k] = v.isoformat()

    return data


def fetch_all(query, params=None):
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        return [row_to_dict(r) for r in result]


def fetch_one(query, params=None):
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        row = result.fetchone()
        return row_to_dict(row)


def query_text(query, params=None):
    """Выполнить произвольный оператор (INSERT/UPDATE/DELETE) и вернуть cursor.

    Используется для создания заказа внутри транзакции.
    """
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        return result


def run_in_transaction(statements):
    """Выполнить список (sql, params) в одной транзакции."""
    with engine.begin() as conn:  # autocommit-транзакция: commit или rollback
        for sql, params in statements:
            conn.execute(text(sql), params or {})
        return True


def transaction():
    """Контекст-менеджер соединения для многошаговых транзакций.

    Возвращает Connection, на котором можно выполнять запросы и получать
    LAST_INSERT_ID() / lastrowid в рамках одного соединения.
    Используется при создании заказа (несколько INSERT с автоинкрементом).
    """
    return engine.begin()
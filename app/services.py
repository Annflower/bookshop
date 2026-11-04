"""Бизнес-логика: товары, категории, заказ, аналитика.

Использует app.db (SQLAlchemy) и переиспользует существующую схему `bookshop_full`.
Принцип: вся работа с БД — параметризованные запросы (безопасно).
"""

from decimal import Decimal
import math
from sqlalchemy import text
from . import db
from . import auth


# --- Авторизация ---
def get_user_by_email(email: str) -> dict | None:
    return db.fetch_one("SELECT * FROM users WHERE email = :email LIMIT 1", {"email": email})


def get_user_by_id(user_id: int) -> dict | None:
    return db.fetch_one("SELECT * FROM users WHERE id = :id", {"id": int(user_id)})


def register_user(payload: dict) -> dict | None:
    """Регистрирует пользователя с хешированным паролем. Возвращает user dict.

    Возвращает None, если email уже занят.
    """
    if get_user_by_email(payload["email"]):
        return None

    pw_hash = auth.hash_password(payload["password"])
    with db.transaction() as conn:
        cur = conn.execute(
            text(
                "INSERT INTO users (name, email, phone, address, city, role, password_hash, created_at, updated_at) "
                "VALUES (:name, :email, :phone, :address, :city, 'user', :pw_hash, NOW(), NULL)"
            ),
            {
                "name": payload["name"],
                "email": payload["email"],
                "phone": payload.get("phone") or None,
                "address": payload.get("address") or None,
                "city": payload.get("city") or None,
                "pw_hash": pw_hash,
            },
        )
        user_id = cur.lastrowid
    return get_user_by_id(user_id)


def authenticate_user(email: str, password: str) -> dict | None:
    """Проверяет email + пароль. Возвращает user dict или None."""
    user = get_user_by_email(email)
    if not user:
        return None
    if not auth.verify_password(password, user.get("password_hash")):
        return None
    return user
def get_products(category_id: int = 0, q: str = "", limit: int = 50, offset: int = 0) -> list:
    base = (
        "SELECT p.*, c.name AS category_name "
        "FROM products p "
        "LEFT JOIN categories c ON p.category_id = c.id "
    )
    params = {}

    if q:
        query = base + "WHERE (p.name LIKE :q OR p.author LIKE :q OR p.description LIKE :q) ORDER BY p.name"
        params["q"] = f"%{q}%"
    elif category_id > 0:
        query = base + "WHERE p.category_id = :category_id ORDER BY p.name"
        params["category_id"] = category_id
    else:
        query = base + "ORDER BY p.created_at DESC"

    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    query += f" LIMIT {limit} OFFSET {offset}"
    return db.fetch_all(query, params)


def get_product(product_id: int) -> dict | None:
    row = db.fetch_one(
        "SELECT p.*, c.name AS category_name "
        "FROM products p LEFT JOIN categories c ON p.category_id = c.id "
        "WHERE p.id = :id",
        {"id": int(product_id)},
    )
    return row


# --- Категории ---
def get_categories() -> list:
    return db.fetch_all("SELECT * FROM categories ORDER BY name")


# --- ИИ-поиск (смарт-матчинг по фразе/описанию) ---
# Стоп-слова русского языка (отбрасываем при анализе фразы)
_STOPWORDS = {
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то",
    "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за",
    "бы", "по", "только", "ее", "мне", "было", "вот", "от", "меня", "еще",
    "нет", "о", "из", "ему", "теперь", "когда", "даже", "ну", "вдруг", "ли",
    "если", "уже", "или", "ни", "быть", "был", "него", "до", "вас", "нибудь",
    "опять", "уж", "вам", "ведь", "там", "потом", "себя", "ничего", "ей",
    "может", "они", "тут", "где", "есть", "надо", "ней", "для", "мы", "тебя",
    "их", "чем", "была", "сам", "чтоб", "без", "будто", "чего", "раз", "тоже",
    "себе", "под", "будет", "ж", "тогда", "кто", "этот", "того", "потому",
    "этого", "какой", "совсем", "ним", "здесь", "этом", "один", "почти",
    "мой", "тем", "чтобы", "нее", "сейчас", "были", "куда", "зачем", "сказать",
    "всех", "никогда", "сегодня", "можно", "при", "наконец", "два", "оба",
    "что-то", "об", "какой-то", "уже", "только", "по", "на", "с", "в",
    "и", "а", "о", "к", "из", "за", "до", "про", "над", "обо", "под",
}

# Псевдонимы/синонимы для тем, чтобы матчиться по смыслу (без полноценных эмбеддингов)
_SYNONYMS = {
    "фантастика": ["фантастик", "космос", "космическ", "марс", "планет", "галактик", "звезд", "инопланет", "будущее", "робот", "научн"],
    "детектив": ["детектив", "преступлен", "расследован", "убийств", "загадк", "сыщик"],
    "любовь": ["любовь", "любовн", "романтика", "роман", "влюб", "страсть", "чувств"],
    "война": ["война", "войн", "воен", "фронт", "сражен", "битв", "солдат"],
    "рисование": ["рисован", "рису", "рисунок", "скетч", "живопис", "акварел", "масл", "карандаш", "краск", "художник", "творчест"],
    "анимация": ["анимац", "мульт", "мультипликац", "2d", "3d", "моушн", "motion", "blender", "персонаж", "сказк"],
    "английский": ["англий", "english", "english grammar", "иностранн"],
    "китайский": ["китай", "китайск", "chinese", "hsб", "иероглиф"],
    "корейский": ["корей", "корейск", "korean", "topik", "хангыль"],
    "детские": ["детск", "сказк", "малыш", "ребенок", "ребят", "приключ"],
    "учебная": ["учеб", "учебник", "пособи", "школ", "класс", "экзамен", "подготовка", "курс"],
    "классика": ["классик", "роман", "повесть", "рассказ", "литератур"],
    "фэнтези": ["фэнтези", "фентези", "маги", "волшеб", "дракон", "эльф", "колдун", "магия"],
}

# Простая нормализация: убираем окончания, чтобы ловить падежи/формы
def _norm_token(w: str) -> str:
    w = w.lower().strip()
    # убираем ё -> е
    w = w.replace("ё", "е")
    # отбрасываем типовые окончания (грубо, для поиска)
    for suf in ("ами", "ями", "ого", "его", "ому", "ему", "ыми", "ими",
                "ая", "яя", "ое", "ее", "ий", "ый", "ой", "ей", "ое", "ое",
                "ов", "ев", "ам", "ям", "ах", "ях", "у", "ю", "е", "а", "я",
                "ы", "и", "о", "ь"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)]
    return w


# Собираем "значимые" слова фразы: без стоп-слов, нормализованные.
# Возвращаем (literal, expanded): literal — дословные токены фразы,
# expanded — синонимические (раскрытие темы). Они ранжируются по-разному,
# чтобы конкретное слово фразы не размывалось общими словами темы.
def _meaning_tokens(phrase: str) -> tuple:
    literal = set()
    for w in phrase.lower().replace("ё", "е").split():
        w = w.strip(".,!?;:()«»\"'-")
        if not w:
            continue
        if w in _STOPWORDS:
            continue
        literal.add(_norm_token(w))

    expanded = set()
    for token in literal:
        for theme, syns in _SYNONYMS.items():
            if token in syns or token.startswith(theme) or theme in token:
                expanded.update(s for s in syns)
    expanded -= literal  # syn-слова не должны дублировать буквальные
    return sorted(literal), sorted(expanded)


def _idf_weights(tokens: list, products: list) -> dict:
    """Вес токена: log((N+1)/(df+1)) + 1 — 'редкие' слова влияют сильнее."""
    n = len(products)
    weights = {}
    for t in tokens:
        df = sum(1 for p in products
                 if t and (t in _norm_token(p["name"] or "")
                           or t in _norm_token(p["author"] or "")
                           or t in _norm_token(p["description"] or "")
                           or t in _norm_token(p["category_name"] or "")))
        weights[t] = math.log((n + 1) / (df + 1)) + 1.0
    return weights


def ai_search(phrase: str, limit: int = 6) -> list:
    """Возвращает книги, релевантные фразе/описанию, с score.

    Реализация — лёгкий смарт-поиск (без внешних моделей): токенизируем фразу,
    нормализуем, взвешиваем по idf (редкость слова), оцениваем совпадение по
    названию/автору/описанию/категории. Полноценная семантика (embeddings) —
    за рамками этого проекта без тяжёлых зависимостей.
    """
    phrase = phrase.strip()
    if not phrase:
        return []

    literal, expanded = _meaning_tokens(phrase)
    if not literal:
        return []

    products = db.fetch_all(
        "SELECT p.*, c.name AS category_name FROM products p "
        "LEFT JOIN categories c ON p.category_id = c.id"
    )

    weights = _idf_weights(literal + expanded, products)

    scored = []
    for p in products:
        name_n = _norm_token(p["name"] or "")
        author_n = _norm_token(p["author"] or "")
        desc_n = _norm_token(p["description"] or "")
        cat_n = _norm_token(p["category_name"] or "")
        haystack = f"{name_n} {author_n} {desc_n} {cat_n}"

        score = 0.0
        # буквальные слова фразы — полный вес
        for t in literal:
            w = weights.get(t, 1.0)
            if not t:
                continue
            factor = 0.0
            if t in name_n:
                factor = max(factor, 1.0)
            if t in author_n:
                factor = max(factor, 1.2)
            if t in desc_n:
                factor = max(factor, 1.2)
            if t in cat_n:
                factor = max(factor, 0.5)
            if factor > 0:
                score += w * factor
            if len(t) > 2 and t in haystack and t not in name_n:
                score += w * 0.3
        # синонимические (раскрытие темы) — приглушённый вес,
        # чтобы конкретное слово фразы не размывалось общими словами темы
        for t in expanded:
            w = weights.get(t, 1.0) * 0.5
            if not t:
                continue
            factor = 0.0
            if t in name_n:
                factor = max(factor, 1.0)
            if t in author_n:
                factor = max(factor, 1.2)
            if t in desc_n:
                factor = max(factor, 1.2)
            if t in cat_n:
                factor = max(factor, 0.5)
            if factor > 0:
                score += w * factor
        if score > 0:
            scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return []
    top = scored[: max(1, int(limit))]
    return [
        {**p, "score": round(float(s), 2)}
        for s, p in top
    ]
def create_order(payload: dict, user_id: int | None = None) -> int | None:
    """Создаёт заказ (покупатель + заказ + состав + статус + событие) в одной транзакции.

    Если передан user_id (авторизованный пользователь) — заказ привязывается к нему,
    а его профиль обновляется. Иначе используется гостевая привязка по email.

    Возвращает id заказа или None при ошибке.
    """
    name = payload["name"]
    email = payload["email"]
    phone = payload["phone"]
    address = payload["address"]
    city = payload.get("city") or None
    items = payload["items"]

    try:
        with db.transaction() as conn:
            # 1. Определяем user_id
            if user_id:
                # авторизованный пользователь
                conn.execute(
                    text("UPDATE users SET name=:name, phone=:phone, address=:address, city=:city, updated_at=NOW() WHERE id=:id"),
                    {"name": name, "phone": phone, "address": address, "city": city, "id": user_id},
                )
            else:
                # гость: ищем/создаём пользователя по email
                user = conn.execute(
                    text("SELECT id FROM users WHERE email = :email LIMIT 1"),
                    {"email": email},
                ).fetchone()
                if user:
                    user_id = user[0]
                    conn.execute(
                        text("UPDATE users SET name=:name, phone=:phone, address=:address, city=:city, updated_at=NOW() WHERE id=:id"),
                        {"name": name, "phone": phone, "address": address, "city": city, "id": user_id},
                    )
                else:
                    cur = conn.execute(
                        text("INSERT INTO users (name, email, phone, address, city, created_at, updated_at) "
                             "VALUES (:name, :email, :phone, :address, :city, NOW(), NULL)"),
                        {"name": name, "email": email, "phone": phone, "address": address, "city": city},
                    )
                    user_id = cur.lastrowid

            # 2. Сумма + проверка товаров
            total = Decimal("0.00")
            enriched = []
            for it in items:
                product = get_product(it["product_id"])
                if not product:
                    return None
                price = Decimal(str(product["base_price"]))
                qty = int(it["quantity"])
                total += price * qty
                enriched.append({
                    "product_id": product["id"],
                    "quantity": qty,
                    "price": float(price),
                    "name": product["name"],
                    "author": product["author"],
                })

            if not enriched:
                return None

            # 3. Заказ
            cur = conn.execute(
                text("INSERT INTO orders (user_id, city, total_amount, status, created_at, updated_at) "
                     "VALUES (:user_id, :city, :total, 'new', NOW(), NULL)"),
                {"user_id": user_id, "city": city, "total": float(total)},
            )
            order_id = cur.lastrowid

            # 4. Состав + списание остатка
            for it in enriched:
                conn.execute(
                    text("INSERT INTO order_items (order_id, product_id, quantity, price, created_at) "
                         "VALUES (:order_id, :product_id, :quantity, :price, NOW())"),
                    {"order_id": order_id, "product_id": it["product_id"],
                     "quantity": it["quantity"], "price": it["price"]},
                )
                conn.execute(
                    text("UPDATE products SET in_stock = in_stock - :qty, updated_at = NOW() WHERE id = :id"),
                    {"qty": it["quantity"], "id": it["product_id"]},
                )

            # 5. Начальный статус
            conn.execute(
                text("INSERT INTO order_status_history (order_id, status_from, status_to, changed_by, changed_at) "
                     "VALUES (:order_id, NULL, 'new', 'customer', NOW())"),
                {"order_id": order_id},
            )

            # 6. Событие (аналитика)
            conn.execute(
                text("INSERT INTO event_log (event_type, session_id, user_id, product_id, order_id, value, meta, created_at) "
                     "VALUES ('order_created', 'api', :user_id, NULL, :order_id, :value, 'order_created_via_api', NOW())"),
                {"user_id": user_id, "order_id": order_id, "value": float(total)},
            )

        return order_id
    except Exception:
        return None


# --- Избранное (wishlist) ---
def get_favorites(user_id: int) -> list:
    """Возвращает список книг в избранном пользователя с категорией."""
    return db.fetch_all(
        "SELECT p.*, c.name AS category_name, f.created_at AS fav_added "
        "FROM favorites f "
        "JOIN products p ON f.product_id = p.id "
        "LEFT JOIN categories c ON p.category_id = c.id "
        "WHERE f.user_id = :uid ORDER BY f.created_at DESC",
        {"uid": int(user_id)},
    )


def add_favorite(user_id: int, product_id: int) -> bool:
    """Добавляет книгу в избранное (идемпотентно). Возвращает True если добавлена."""
    product = get_product(product_id)
    if not product:
        return False
    # Предотвращаем дубликат редким INSERT IGNORE (или ON DUPLICATE KEY)
    db.run_in_transaction([
        (
            "INSERT IGNORE INTO favorites (user_id, product_id) VALUES (:uid, :pid)",
            {"uid": int(user_id), "pid": int(product_id)},
        )
    ])
    return True


# --- Жалобы / брак / проблемы с книгой ---
def create_complaint(payload: dict, user_id: int | None = None) -> int | None:
    """Создаёт заявку о проблеме с книгой (гость или авторизованный).

    Возвращает id заявки или None, если товар не найден / данные неполные.
    """
    product = get_product(payload["product_id"])
    if not product:
        return None

    if user_id is None:
        req_user_id = payload.get("user_id") or None
    else:
        req_user_id = user_id

    with db.transaction() as conn:
        cur = conn.execute(
            text(
                "INSERT INTO complaints (product_id, user_id, name, email, phone, issue_type, description, status, created_at) "
                "VALUES (:product_id, :user_id, :name, :email, :phone, :issue_type, :description, 'new', NOW())"
            ),
            {
                "product_id": int(payload["product_id"]),
                "user_id": req_user_id,
                "name": payload["name"],
                "email": payload["email"],
                "phone": payload.get("phone") or None,
                "issue_type": payload.get("issue_type", "damage"),
                "description": payload["description"],
            },
        )
        complaint_id = cur.lastrowid

    # Событие для аналитики
    db.run_in_transaction([
        ("INSERT INTO event_log (event_type, session_id, user_id, product_id, order_id, value, meta, created_at) "
         "VALUES ('complaint_created', 'api', :user_id, :product_id, NULL, NULL, :meta, NOW())",
         {"user_id": req_user_id, "product_id": int(payload["product_id"]),
          "meta": f"issue={payload.get('issue_type', 'damage')} id={complaint_id}"}),
    ])

    return complaint_id


def get_complaints(status: str = "", limit: int = 100, offset: int = 0) -> list:
    """Список жалоб для админ-панели (с названием товара)."""
    where, params = "", {}
    if status:
        where = " WHERE c.status = :status"
        params["status"] = status
    limit = max(1, min(int(limit), 1000))
    offset = max(0, int(offset))
    return db.fetch_all(
        "SELECT c.*, p.name AS product_name "
        "FROM complaints c LEFT JOIN products p ON c.product_id = p.id"
        + where +
        f" ORDER BY c.created_at DESC LIMIT {limit} OFFSET {offset}",
        params,
    )


def update_complaint_status(complaint_id: int, status: str) -> bool:
    """Обновляет статус жалобы (только валидные значения)."""
    allowed = {"new", "processing", "resolved", "rejected"}
    if status not in allowed:
        return False
    complaint = db.fetch_one("SELECT * FROM complaints WHERE id = :id", {"id": complaint_id})
    if not complaint:
        return False
    db.run_in_transaction([
        ("UPDATE complaints SET status=:status, updated_at=NOW() WHERE id=:id",
         {"status": status, "id": complaint_id}),
    ])
    return True


def remove_favorite(user_id: int, product_id: int) -> bool:
    """Удаляет книгу из избранного. Возвращает True если была удалена."""
    db.run_in_transaction([
        ("DELETE FROM favorites WHERE user_id = :uid AND product_id = :pid",
         {"uid": int(user_id), "pid": int(product_id)}),
    ])
    return True


def is_favorite(user_id: int, product_id: int) -> bool:
    row = db.fetch_one(
        "SELECT 1 AS x FROM favorites WHERE user_id = :uid AND product_id = :pid LIMIT 1",
        {"uid": int(user_id), "pid": int(product_id)},
    )
    return bool(row)


# --- Аналитика (витрины) ---
def get_analytics(view: str, event_type: str = "", limit: int = 100, offset: int = 0) -> list | None:
    if view == "order-facts":
        return db.fetch_all("SELECT * FROM v_order_facts ORDER BY order_date DESC")
    if view == "product-sales":
        return db.fetch_all("SELECT * FROM v_product_sales ORDER BY order_date_day DESC, line_total DESC")
    if view == "daily-revenue":
        return db.fetch_all("SELECT * FROM v_daily_revenue ORDER BY revenue_date DESC")

    if view == "event-log":
        where, params = "", {}
        if event_type:
            where = " WHERE event_type = :event_type"
            params["event_type"] = event_type
        limit = max(1, min(int(limit), 1000))
        offset = max(0, int(offset))
        return db.fetch_all(
            "SELECT * FROM v_event_log" + where + f" ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}",
            params,
        )

    return None


# --- Статусы заказов (для дашборда / смены статуса) ---
def update_order_status(order_id: int, status: str) -> bool:
    allowed = {"new", "processing", "shipped", "completed", "cancelled"}
    if status not in allowed:
        return False

    order = db.fetch_one("SELECT * FROM orders WHERE id = :id", {"id": order_id})
    if not order:
        return False

    old = order["status"]
    db.run_in_transaction([
        ("UPDATE orders SET status=:status, updated_at=NOW() WHERE id=:id", {"status": status, "id": order_id}),
        ("INSERT INTO order_status_history (order_id, status_from, status_to, changed_by, changed_at) "
         "VALUES (:order_id, :from, :to, 'admin', NOW())",
         {"order_id": order_id, "from": old, "to": status}),
        ("INSERT INTO event_log (event_type, session_id, user_id, product_id, order_id, value, meta, created_at) "
         "VALUES ('order_status_changed', 'api', NULL, NULL, :order_id, :value, :meta, NOW())",
         {"order_id": order_id, "value": float(order["total_amount"]), "meta": f"{old} -> {status}"}),
    ])
    return True


# --- Администратор (вход в аналитику) ---
def get_admin_by_email(email: str) -> dict | None:
    """Возвращает пользователя только если у него роль admin."""
    user = get_user_by_email(email)
    if not user or user.get("role") != "admin":
        return None
    return user


# --- Аналитика: сводные KPI ---
def get_analytics_kpi() -> dict:
    """Сводные показатели: всего заказов, выручка, клиенты, средний чек,
    отзывы, открытые жалобы, города."""
    row = db.fetch_one(
        "SELECT COUNT(*) AS orders_total, "
        "COUNT(DISTINCT user_id) AS customers_total, "
        "COALESCE(SUM(total_amount),0) AS revenue_total, "
        "COALESCE(AVG(total_amount),0) AS avg_order, "
        "(SELECT COUNT(*) FROM reviews) AS reviews_total, "
        "(SELECT COUNT(*) FROM complaints WHERE status IN ('new','processing')) AS complaints_open "
        "FROM orders WHERE status <> 'cancelled'"
    ) or {}
    cities = db.fetch_one(
        "SELECT COUNT(DISTINCT city) AS cities_total FROM orders WHERE city IS NOT NULL AND city <> ''"
    ) or {}
    row["cities_total"] = cities.get("cities_total", 0)
    return row


# --- Аналитика: города ---
def get_analytics_cities() -> list:
    """Топ городов по числу заказов и выручке."""
    return db.fetch_all(
        "SELECT o.city, COUNT(DISTINCT o.id) AS orders_count, "
        "COUNT(DISTINCT o.user_id) AS customers_count, "
        "COALESCE(SUM(o.total_amount),0) AS revenue "
        "FROM orders o WHERE o.city IS NOT NULL AND o.city <> '' AND o.status <> 'cancelled' "
        "GROUP BY o.city ORDER BY revenue DESC, orders_count DESC"
    )


# --- Аналитика: отзывы ---
def get_analytics_reviews(limit: int = 100, offset: int = 0) -> list:
    """Список отзывов с именем пользователя и названием книги."""
    limit = max(1, min(int(limit), 1000))
    offset = max(0, int(offset))
    return db.fetch_all(
        "SELECT r.id, r.product_id, r.user_id, r.rating, r.text, r.created_at, "
        "u.name AS user_name, p.name AS product_name "
        "FROM reviews r "
        "JOIN users u ON r.user_id = u.id "
        "JOIN products p ON r.product_id = p.id "
        f"ORDER BY r.created_at DESC LIMIT {limit} OFFSET {offset}"
    )
"""FastAPI-приложение bookshop_py.

REST API поверх существующей БД `bookshop_full` (та же схема, что и в PHP-версии).
Публичные и защищённые (Bearer-токен) эндпоинты + отдача frontend/.
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import FileResponse, JSONResponse

from . import db
from . import services
from . import schemas
from . import auth

app = FastAPI(
    title="bookshop_py API",
    description="Книжный магазин + аналитика (переиспользует БД bookshop_full)",
    version="1.0.0",
)

# --- Frontend (HTML+JS) отдаётся из папки frontend/ ---


@app.get("/", include_in_schema=False)
def index():
    return FileResponse("frontend/index.html")


@app.get("/style.css", include_in_schema=False)
def style():
    return FileResponse("frontend/style.css")


@app.get("/app.js", include_in_schema=False)
def app_js():
    return FileResponse("frontend/app.js")


# --- Защита аналитических эндпоинтов (администратор) ---


def optional_user(authorization: str = Header(default="")):
    """Возвращает пользователя из токена или None, если токена нет/невалиден.

    Используется в заказе: заказ привязывается к аккаунту, если пользователь вошёл,
    иначе создаётся гостевой заказ.
    """
    token = ""
    if authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    elif authorization:
        token = authorization.strip()
    user_id = auth.decode_token(token) if token else None
    if not user_id:
        return None
    return services.get_user_by_id(user_id)


def current_user(authorization: str = Header(default="")):
    """Достаёт пользователя из подписанного токена (для /me и персональных заказов)."""
    user = optional_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Необходимо войти в аккаунт")
    return user


def require_admin(user: dict = Depends(current_user)):
    """Аналитика и управление жалобами доступны только пользователю с ролью admin."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Доступ только для администратора")
    return user


# --- Публичные: товары и категории ---


@app.get("/api/products", response_model=list[schemas.ProductOut])
def api_products(
    category: int = 0,
    q: str = "",
    limit: int = 50,
    offset: int = 0,
):
    return services.get_products(category_id=category, q=q, limit=limit, offset=offset)


@app.get("/api/products/{product_id}", response_model=schemas.ProductOut)
def api_product(product_id: int):
    product = services.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return product


@app.get("/api/categories", response_model=list[schemas.CategoryOut])
def api_categories():
    return services.get_categories()


# --- Публичные: заказ ---


@app.post("/api/orders", response_model=schemas.OrderOut, status_code=201)
def api_create_order(
    payload: schemas.OrderCreateIn,
    user: dict | None = Depends(optional_user),
):
    user_id = user["id"] if user else None
    order_id = services.create_order(payload.model_dump(), user_id=user_id)
    if not order_id:
        raise HTTPException(status_code=400, detail="Не удалось создать заказ (проверьте товары и остатки)")

    order = db.fetch_one("SELECT id, total_amount, status FROM orders WHERE id=:id", {"id": order_id})
    return {
        "order_id": order_id,
        "total_amount": order["total_amount"],
        "status": order["status"],
    }


# --- ИИ-поиск (смарт-матчинг по фразе/описанию) ---


@app.post("/api/ai/search")
def api_ai_search(payload: schemas.AiSearchIn):
    results = services.ai_search(payload.query, limit=payload.limit or 6)
    return {"success": True, "query": payload.query, "results": results}


# --- Избранное (wishlist) ---


@app.get("/api/favorites", response_model=list[schemas.FavoriteOut])
def api_list_favorites(user: dict = Depends(current_user)):
    return services.get_favorites(user["id"])


@app.post("/api/favorites", response_model=schemas.FavoriteStatus)
def api_add_favorite(
    payload: schemas.FavoriteIn,
    user: dict = Depends(current_user),
):
    ok = services.add_favorite(user["id"], payload.product_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Книга не найдена")
    return {"in_favorites": True}


@app.delete("/api/favorites/{product_id}", response_model=schemas.FavoriteStatus)
def api_remove_favorite(product_id: int, user: dict = Depends(current_user)):
    services.remove_favorite(user["id"], product_id)
    return {"in_favorites": False}


@app.get("/api/favorites/{product_id}", response_model=schemas.FavoriteStatus)
def api_is_favorite(product_id: int, user: dict = Depends(current_user)):
    return {"in_favorites": services.is_favorite(user["id"], product_id)}


# --- Жалобы / брак / проблемы с книгой ---


@app.post("/api/complaints", response_model=schemas.ComplaintOut, status_code=201)
def api_create_complaint(
    payload: schemas.ComplaintCreateIn,
    user: dict | None = Depends(optional_user),
):
    """Публичный эндпоинт: клиент сообщает о проблеме с книгой (брак и т.д.)."""
    user_id = user["id"] if user else None
    complaint_id = services.create_complaint(payload.model_dump(), user_id=user_id)
    if not complaint_id:
        raise HTTPException(status_code=404, detail="Книга не найдена")
    complaint = db.fetch_one(
        "SELECT c.*, p.name AS product_name FROM complaints c "
        "LEFT JOIN products p ON c.product_id = p.id WHERE c.id = :id",
        {"id": complaint_id},
    )
    return complaint


@app.get("/api/complaints", response_model=list[schemas.ComplaintOut])
def api_list_complaints(
    status: str = "",
    limit: int = 100,
    offset: int = 0,
    _: None = Depends(require_admin),
):
    """Админ: список жалоб."""
    return services.get_complaints(status=status, limit=limit, offset=offset)


@app.patch("/api/complaints/{complaint_id}", response_model=schemas.ComplaintOut)
def api_update_complaint_status(
    complaint_id: int,
    payload: schemas.ComplaintStatusIn,
    _: None = Depends(require_admin),
):
    """Админ: смена статуса жалобы."""
    ok = services.update_complaint_status(complaint_id, payload.status)
    if not ok:
        raise HTTPException(status_code=404, detail="Жалоба не найдена или неверный статус")
    complaint = db.fetch_one(
        "SELECT c.*, p.name AS product_name FROM complaints c "
        "LEFT JOIN products p ON c.product_id = p.id WHERE c.id = :id",
        {"id": complaint_id},
    )
    return complaint


# --- Защищённые: аналитика ---


@app.get("/api/analytics/order-facts")
def api_order_facts(_: None = Depends(require_admin)):
    data = services.get_analytics("order-facts")
    return {"success": True, "data": data}


@app.get("/api/analytics/product-sales")
def api_product_sales(_: None = Depends(require_admin)):
    data = services.get_analytics("product-sales")
    return {"success": True, "data": data}


@app.get("/api/analytics/daily-revenue")
def api_daily_revenue(_: None = Depends(require_admin)):
    data = services.get_analytics("daily-revenue")
    return {"success": True, "data": data}


@app.get("/api/analytics/event-log")
def api_event_log(
    event_type: str = "",
    limit: int = 100,
    offset: int = 0,
    _: None = Depends(require_admin),
):
    data = services.get_analytics("event-log", event_type=event_type, limit=limit, offset=offset)
    return {"success": True, "data": data}


@app.get("/api/analytics/kpi")
def api_analytics_kpi(_: None = Depends(require_admin)):
    data = services.get_analytics_kpi()
    return {"success": True, "data": data}


@app.get("/api/analytics/cities")
def api_analytics_cities(_: None = Depends(require_admin)):
    data = services.get_analytics_cities()
    return {"success": True, "data": data}


@app.get("/api/analytics/reviews", response_model=list[schemas.ReviewOut])
def api_analytics_reviews(
    limit: int = 100,
    offset: int = 0,
    _: None = Depends(require_admin),
):
    return services.get_analytics_reviews(limit=limit, offset=offset)


# --- Авторизация ---


@app.post("/api/auth/register", response_model=schemas.TokenOut, status_code=201)
def api_register(payload: schemas.RegisterIn):
    user = services.register_user(payload.model_dump())
    if not user:
        raise HTTPException(status_code=409, detail="Пользователь с таким email уже существует")
    token = auth.create_token(user["id"])
    return {"token": token, "user": user}


@app.post("/api/auth/login", response_model=schemas.TokenOut)
def api_login(payload: schemas.LoginIn):
    user = services.authenticate_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    token = auth.create_token(user["id"])
    return {"token": token, "user": user}


@app.get("/api/auth/me", response_model=schemas.UserOut)
def api_me(user: dict = Depends(current_user)):
    return user


# --- Здоровье ---


@app.get("/api/health")
def health():
    try:
        db.fetch_one("SELECT 1 AS ok")
        return {"success": True, "data": {"status": "ok", "db": True}}
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"success": False, "error": {"message": str(e)}})
"""Pydantic-схемы (валидация входных/выходных данных) для API."""

from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class ProductOut(BaseModel):
    id: int
    category_id: Optional[int] = None
    name: str
    author: Optional[str] = None
    base_price: float
    in_stock: int
    description: Optional[str] = None
    image: Optional[str] = None
    category_name: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CategoryOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int = Field(ge=1)


class OrderCreateIn(BaseModel):
    name: str
    email: EmailStr
    phone: str
    address: str
    city: Optional[str] = None
    items: List[OrderItemIn]


class OrderOut(BaseModel):
    order_id: int
    total_amount: float
    status: str


class MailIn(BaseModel):
    """Не используется — заглушка для совместимости схем API (опционально)."""
    to: str
    subject: str
    body: str


# ---------- ИИ-поиск ----------
class AiSearchIn(BaseModel):
    query: str
    limit: int = Field(default=6, ge=1, le=20)


# ---------- Избранное (wishlist) ----------
class FavoriteIn(BaseModel):
    product_id: int


class FavoriteStatus(BaseModel):
    in_favorites: bool


class FavoriteOut(BaseModel):
    """Строка избранного = товар с полем fav_added (когда добавлен)."""
    id: int
    category_id: Optional[int] = None
    name: str
    author: Optional[str] = None
    base_price: float
    in_stock: int
    description: Optional[str] = None
    image: Optional[str] = None
    category_name: Optional[str] = None
    fav_added: Optional[str] = None


# ---------- Авторизация ----------
class RegisterIn(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    created_at: Optional[str] = None


class TokenOut(BaseModel):
    token: str
    user: UserOut


# ---------- Жалобы / брак / проблемы с книгой ----------
class ComplaintCreateIn(BaseModel):
    """Заявка о проблеме с книгой (брак, повреждение, не та книга и т.д.)."""
    product_id: int
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: Optional[str] = None
    issue_type: str = Field(default="damage")
    description: str = Field(min_length=1)


class ComplaintStatusIn(BaseModel):
    """Смена статуса жалобы (для админа)."""
    status: str


class ComplaintOut(BaseModel):
    id: int
    product_id: int
    user_id: Optional[int] = None
    name: str
    email: str
    phone: Optional[str] = None
    issue_type: str
    description: str
    status: str
    created_at: Optional[str] = None
    product_name: Optional[str] = None


# ---------- Отзывы (reviews) ----------
class ReviewOut(BaseModel):
    id: int
    product_id: int
    user_id: int
    rating: int
    text: Optional[str] = None
    created_at: Optional[str] = None
    user_name: Optional[str] = None
    product_name: Optional[str] = None
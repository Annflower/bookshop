"""Авторизация: хеширование паролей и подписанные токены (без внешних зависимостей).

Пароль — PBKDF2-HMAC-SHA256 (stdlib). Токен — самоподписанный:
    base64url(user_id.expiry.sig), где sig = HMAC-SHA256(user_id.expiry, JWT_SECRET).
Всё совместимо с Python 3.14 и не требует passlib/bcrypt/jwt.
"""

import base64
import hashlib
import hmac
import os
import time

from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "change-this-secret-in-production-please",
)

# Параметры PBKDF2
_PBKDF2_ALGO = "sha256"
_PBKDF2_ITER = 120_000
_SALT_BYTES = 16
_TOKEN_TTL_SEC = 60 * 60 * 24 * 7  # 7 дней


# ---------- Пароли ----------
def hash_password(password: str) -> str:
    """Возвращает строку `iter$salt_hex$digest_hex` для сохранения в БД."""
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        _PBKDF2_ALGO, password.encode("utf-8"), salt, _PBKDF2_ITER
    )
    return f"{_PBKDF2_ITER}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    """Проверяет пароль по строке из БД. Сравнение — в постоянном времени."""
    if not stored:
        return False
    try:
        iterations, salt_hex, digest_hex = stored.split("$", 2)
        iterations = int(iterations)
    except (ValueError, AttributeError):
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac(
        _PBKDF2_ALGO, password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(actual, expected)


# ---------- Токены ----------
def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _sign(payload: str) -> str:
    mac = hmac.new(JWT_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256)
    return _b64e(mac.digest())


def create_token(user_id: int) -> str:
    """Создаёт подписанный токен на TTL (7 дней)."""
    expiry = int(time.time()) + _TOKEN_TTL_SEC
    payload = f"{user_id}.{expiry}"
    return _b64e(payload.encode("ascii")) + "." + _sign(payload)


def decode_token(token: str) -> int | None:
    """Возвращает user_id или None, если токен невалиден/истёк/подделан."""
    try:
        token = token.strip()
        if "." not in token:
            return None
        b64_payload, sig = token.rsplit(".", 1)
        payload = _b64d(b64_payload).decode("ascii")
        if not hmac.compare_digest(_sign(payload), sig):
            return None
        user_id_str, expiry_str = payload.split(".", 1)
        if int(expiry_str) < time.time():
            return None
        return int(user_id_str)
    except Exception:
        return None
-- Таблица избранного (wishlist): один пользователь может сохранить книгу.
-- Дубликаты (user, product) запрещены, добавление — идемпотентно.
-- Применяется поверх существующей БД bookshop_full.
USE bookshop_full;

CREATE TABLE IF NOT EXISTS favorites (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    product_id INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_favorites_user_product (user_id, product_id),
    KEY idx_favorites_product (product_id),
    CONSTRAINT fk_favorites_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_favorites_product
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

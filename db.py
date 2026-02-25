import aiosqlite

DB_PATH = "bot.db"


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price INTEGER NOT NULL,
            description TEXT DEFAULT ''
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS carts (
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            PRIMARY KEY (user_id, product_id)
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'NEW'
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            qty INTEGER NOT NULL
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, product_id) -- 1 marta review
        );
        """)
        await db.commit()


async def seed_products_if_empty() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM products;")
        (cnt,) = await cur.fetchone()
        if cnt > 0:
            return

        sample = [
            ("Namlantiruvchi krem", "Yuz parvarishi", 85000, "Quruq teri uchun namlantiradi."),
            ("Yuvish geli", "Tonik/Yuvish", 60000, "Yog‘li teri uchun yumshoq yuvish."),
        ]
        await db.executemany(
            "INSERT INTO products(name, category, price, description) VALUES(?,?,?,?)",
            sample
        )
        await db.commit()


# ---------- Catalog ----------
async def list_categories():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT DISTINCT category FROM products ORDER BY category;")
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def list_products_by_category(category: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, name, price FROM products WHERE category=? ORDER BY id DESC;",
            (category,)
        )
        return await cur.fetchall()


async def get_product(product_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, name, category, price, description FROM products WHERE id=?;",
            (product_id,)
        )
        return await cur.fetchone()


# ---------- Cart ----------
async def add_to_cart(user_id: int, product_id: int, qty: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO carts(user_id, product_id, qty)
        VALUES(?,?,?)
        ON CONFLICT(user_id, product_id) DO UPDATE SET qty = qty + excluded.qty;
        """, (user_id, product_id, qty))
        await db.commit()


async def get_cart(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
        SELECT p.id, p.name, p.price, c.qty
        FROM carts c
        JOIN products p ON p.id=c.product_id
        WHERE c.user_id=?
        ORDER BY p.id DESC;
        """, (user_id,))
        return await cur.fetchall()


async def clear_cart(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM carts WHERE user_id=?;", (user_id,))
        await db.commit()


# ---------- Orders ----------
async def create_order_from_cart(user_id: int, full_name: str, phone: str, address: str) -> int:
    cart = await get_cart(user_id)
    if not cart:
        raise ValueError("Cart is empty")

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
        INSERT INTO orders(user_id, full_name, phone, address, status)
        VALUES(?,?,?,?, 'NEW');
        """, (user_id, full_name, phone, address))
        order_id = cur.lastrowid

        items = [(order_id, pid, name, price, qty) for (pid, name, price, qty) in cart]
        await db.executemany("""
        INSERT INTO order_items(order_id, product_id, name, price, qty)
        VALUES(?,?,?,?,?);
        """, items)

        await db.execute("DELETE FROM carts WHERE user_id=?;", (user_id,))
        await db.commit()
        return int(order_id)


async def get_order(order_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, user_id, full_name, phone, address, status FROM orders WHERE id=?;",
            (order_id,)
        )
        return await cur.fetchone()


async def get_order_items(order_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT product_id, name, price, qty FROM order_items WHERE order_id=?;",
            (order_id,)
        )
        return await cur.fetchall()


async def set_order_status(order_id: int, status: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE orders SET status=? WHERE id=?;", (status, order_id))
        await db.commit()


# ---------- Reviews ----------
async def eligible_products_for_review(user_id: int, order_id: int):
    """
    Delivered bo'lgan order ichidagi, hali user review yozmagan productlar.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
        SELECT oi.product_id, oi.name
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        WHERE o.id=? AND o.user_id=? AND o.status='DELIVERED'
          AND NOT EXISTS (
            SELECT 1 FROM reviews r WHERE r.user_id=? AND r.product_id=oi.product_id
          )
        ORDER BY oi.product_id DESC;
        """, (order_id, user_id, user_id))
        return await cur.fetchall()


async def add_review(user_id: int, product_id: int, order_id: int, rating: int, text: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO reviews(user_id, product_id, order_id, rating, text)
        VALUES(?,?,?,?,?);
        """, (user_id, product_id, order_id, rating, text))
        await db.commit()


async def get_reviews_for_product(product_id: int, limit: int = 3):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
        SELECT rating, text, created_at
        FROM reviews
        WHERE product_id=?
        ORDER BY created_at DESC
        LIMIT ?;
        """, (product_id, limit))
        return await cur.fetchall()

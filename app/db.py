"""Repository layer helpers: SQLite connection and schema (PostgreSQL in production)."""
import sqlite3
from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
 email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'customer'
 CHECK(role IN ('customer','admin')), address TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS books(book_id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, author TEXT NOT NULL,
 genre TEXT NOT NULL, isbn TEXT UNIQUE NOT NULL, price REAL NOT NULL CHECK(price>0), stock INTEGER NOT NULL CHECK(stock>=0),
 description TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS reviews(review_id INTEGER PRIMARY KEY AUTOINCREMENT, book_id INTEGER NOT NULL REFERENCES books ON DELETE CASCADE,
 user_id INTEGER NOT NULL REFERENCES users, rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5), comment TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS cart_items(cart_item_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users,
 book_id INTEGER NOT NULL REFERENCES books ON DELETE CASCADE, quantity INTEGER NOT NULL CHECK(quantity>=1));
CREATE TABLE IF NOT EXISTS orders(order_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL REFERENCES users,
 total REAL NOT NULL, status TEXT NOT NULL CHECK(status IN ('Pending','Confirmed','Shipped','Delivered','Cancelled')),
 created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS order_items(order_item_id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL REFERENCES orders,
 book_id INTEGER NOT NULL, quantity INTEGER NOT NULL, unit_price REAL NOT NULL);
CREATE TABLE IF NOT EXISTS payments(payment_id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER NOT NULL REFERENCES orders,
 amount REAL NOT NULL, status TEXT NOT NULL CHECK(status IN ('Success','Failed')), txn_ref TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires REAL NOT NULL);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


def close_db(_=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(path):
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.commit()
    con.close()

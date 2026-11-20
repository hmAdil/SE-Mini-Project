"""Seed data: 10 books, one admin, one test customer."""
import sqlite3
import sys

from app.db import init_db
from app.security import hash_password

BOOKS = [
    ("Clean Code", "Robert C. Martin", "Technology", "9780132350884", 450, 12, "A handbook of agile software craftsmanship."),
    ("The Pragmatic Programmer", "Andrew Hunt", "Technology", "9780135957059", 520, 8, "Journey to mastery for developers."),
    ("Refactoring", "Martin Fowler", "Technology", "9780134757599", 350, 20, "Improving the design of existing code."),
    ("To Kill a Mockingbird", "Harper Lee", "Fiction", "9780061120084", 299, 15, "A classic of modern American literature."),
    ("1984", "George Orwell", "Fiction", "9780451524935", 250, 10, "A dystopian social science fiction novel."),
    ("The Alchemist", "Paulo Coelho", "Fiction", "9780062315007", 320, 18, "A fable about following your dream."),
    ("Sapiens", "Yuval Noah Harari", "History", "9780062316097", 499, 9, "A brief history of humankind."),
    ("Atomic Habits", "James Clear", "Self-Help", "9780735211292", 399, 25, "Tiny changes, remarkable results."),
    ("The Selfish Gene", "Richard Dawkins", "Science", "9780198788607", 380, 6, "A gene-centred view of evolution."),
    ("A Brief History of Time", "Stephen Hawking", "Science", "9780553380163", 410, 4, "From the Big Bang to black holes."),
]


def seed(path):
    init_db(path)
    con = sqlite3.connect(path)
    con.executemany(
        "INSERT OR IGNORE INTO books(title,author,genre,isbn,price,stock,description) VALUES(?,?,?,?,?,?,?)", BOOKS)
    con.execute("INSERT OR IGNORE INTO users(name,email,password_hash,role) VALUES('Admin','admin@bookstore.com',?,'admin')",
                (hash_password("Admin@1234"),))
    con.execute("INSERT OR IGNORE INTO users(name,email,password_hash,role) VALUES('Asha','asha@test.com',?,'customer')",
                (hash_password("Pass@1234"),))
    con.commit()
    con.close()


if __name__ == "__main__":
    seed(sys.argv[1] if len(sys.argv) > 1 else "bookstore.db")

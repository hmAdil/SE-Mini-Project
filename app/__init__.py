import os

from flask import Flask, send_from_directory

from .db import close_db, init_db


def create_app(config=None):
    app = Flask(__name__, static_folder="static")
    app.config["DATABASE"] = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bookstore.db")
    app.config.update(config or {})
    init_db(app.config["DATABASE"])
    app.teardown_appcontext(close_db)

    from . import auth, catalog, orders, admin
    for m in (auth, catalog, orders, admin):
        app.register_blueprint(m.bp)

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    return app

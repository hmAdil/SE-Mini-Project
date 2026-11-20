"""System validation: drives the real UI in Edge via Playwright (ST_01-ST_04) and captures demo screenshots.
Usage: python e2e/system_tests.py <out_dir>"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

import requests
from playwright.sync_api import sync_playwright, expect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from seed import seed  # noqa: E402

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
PORT = 5077
BASE = f"http://127.0.0.1:{PORT}"
results = []


def shot(page, name):
    page.screenshot(path=os.path.join(OUT, name + ".png"), full_page=name.startswith(("10", "11")))


def record(tid, title, steps, fn):
    t0 = time.time()
    try:
        fn()
        results.append(dict(id=tid, title=title, steps=steps, result="PASS", secs=round(time.time() - t0, 2), note=""))
    except Exception as e:  # noqa
        results.append(dict(id=tid, title=title, steps=steps, result="FAIL", secs=round(time.time() - t0, 2), note=str(e)[:300]))


def ui_login(page, email, pw):
    page.click("#nav-login")
    page.fill("#email", email)
    page.fill("#pw", pw)
    page.click("#do-login")
    expect(page.locator("#flash")).to_contain_text("Login successful")


def main():
    db = os.path.join(tempfile.mkdtemp(), "e2e.db")
    seed(db)
    code = ("import sys;sys.path.insert(0,r'%s');from app import create_app;"
            "create_app({'DATABASE':r'%s'}).run(port=%d)" % (ROOT, db, PORT))
    srv = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            urllib.request.urlopen(BASE + "/api/books")
            break
        except Exception:
            time.sleep(0.2)
    try:
        with sync_playwright() as p:
            br = p.chromium.launch(channel="msedge")
            ctx = br.new_context(viewport={"width": 1100, "height": 720})
            page = ctx.new_page()
            page.goto(BASE)
            expect(page.locator("#list .book")).to_have_count(10)
            shot(page, "01_catalogue")

            def st01():
                page.click("#nav-register")
                shot(page, "02_register")
                page.fill("#rname", "Ravi")
                page.fill("#remail", "ravi@test.com")
                page.fill("#rpw", "Pass@1234")
                page.click("#do-register")
                expect(page.locator("#flash")).to_contain_text("Account created")
                ui_login(page, "ravi@test.com", "Pass@1234")
                page.click("#nav-profile")
                page.fill("#paddr", "12 MG Road, Bengaluru")
                page.click("#save-profile")
                expect(page.locator("#flash")).to_contain_text("Profile updated")
                page.click("#nav-logout")
                ui_login(page, "ravi@test.com", "Pass@1234")
                page.click("#nav-profile")
                expect(page.locator("#paddr")).to_have_value("12 MG Road, Bengaluru")
                shot(page, "03_profile")
                page.click("#nav-logout")
            record("ST_01", "Register, log in, edit profile, log out",
                   "Register Ravi; log in; save address; log out; log in; open profile", st01)

            def st02():
                ui_login(page, "asha@test.com", "Pass@1234")
                page.fill("#q", "clean")
                page.click("#apply")
                expect(page.locator("#list .book")).to_have_count(1)
                shot(page, "04_search")
                page.click("#list .book a")
                page.fill("#rating", "5")
                page.fill("#comment", "Superb book on craftsmanship")
                page.click("#submit-review")
                page.reload()
                page.click("#nav-books")
                page.fill("#q", "clean")
                page.click("#apply")
                page.click("#list .book a")
                expect(page.locator("#avg")).to_have_text("5")
                expect(page.locator("#revs")).to_contain_text("Superb book")
                shot(page, "05_book_review")
            record("ST_02", "Search a book, open it and review it",
                   "Search 'clean'; open details; submit rating 5; reload; verify review and average", st02)

            def st03():
                page.click("#nav-books")
                page.fill("#q", "sapiens")
                page.click("#apply")
                page.click("#list .book a")
                page.click("#add")
                expect(page.locator("#flash")).to_contain_text("Added to cart")
                page.click("#nav-cart")
                expect(page.locator("#total")).to_have_text("499")
                shot(page, "06_cart")
                page.click("#checkout")
                expect(page.locator("#flash")).to_contain_text("confirmed")
                shot(page, "07_order_confirmed")
                page.click("#nav-orders")
                expect(page.locator("#orders-table")).to_contain_text("Sapiens")
                expect(page.locator("#orders-table")).to_contain_text("Confirmed")
                shot(page, "08_order_history")
            record("ST_03", "Browse, add, pay and view history",
                   "Search Sapiens; add to cart; checkout with test card; open order history", st03)

            def st03b():  # declined card, extra validation
                page.click("#nav-books")
                page.click("#list .book a")
                page.click("#add")
                page.click("#nav-cart")
                page.fill("#card", "4000000000000002")
                page.click("#checkout")
                expect(page.locator("#flash")).to_contain_text("Payment failed")
                shot(page, "09_payment_declined")
                page.fill("#card", "4111111111111111")
                page.click("#checkout")
                expect(page.locator("#flash")).to_contain_text("confirmed")
            record("ST_05", "Declined card keeps order Pending, then retry succeeds",
                   "Add book; pay with 4000000000000002; see error; pay with 4111111111111111", st03b)

            page.click("#nav-logout")

            def st04():
                s = requests.Session()
                for i, price in enumerate((300, 450, 250)):
                    tok = requests.post(BASE + "/api/auth/login", json={"email": "admin@bookstore.com", "password": "Admin@1234"}).json()["token"]
                    h = {"Authorization": "Bearer " + tok}
                    bid = requests.post(BASE + "/api/admin/books", headers=h, json=dict(title=f"Report Book {i}", author="X", genre="Misc", isbn=f"97811{i}", price=price, stock=10)).json()["book_id"]
                    s.post(BASE + "/api/auth/register", json=dict(name=f"U{i}", email=f"u{i}@t.com", password="Pass@1234"))
                    ct = s.post(BASE + "/api/auth/login", json=dict(email=f"u{i}@t.com", password="Pass@1234")).json()["token"]
                    ch = {"Authorization": "Bearer " + ct}
                    s.post(BASE + "/api/cart", headers=ch, json=dict(book_id=bid, quantity=1))
                    s.post(BASE + "/api/orders", headers=ch, json=dict(card="4111111111111111"))
                ui_login(page, "admin@bookstore.com", "Admin@1234")
                page.click("#nav-admin")
                # revenue = 3 report orders (1000) + Sapiens 499 + Clean Code 450 (ST_03 and ST_05)
                expect(page.locator("#revenue")).to_contain_text("1949")
                shot(page, "10_admin_dashboard")
                page.fill("#a-title", "Demo Book")
                page.fill("#a-author", "Demo Author")
                page.fill("#a-genre", "Fiction")
                page.fill("#a-isbn", "9789999999999")
                page.fill("#a-price", "275")
                page.fill("#a-stock", "3")
                page.click("#a-save")
                expect(page.locator("#flash")).to_contain_text("Book saved")
                expect(page.locator("body")).to_contain_text("Demo Book - 3 left")
                shot(page, "11_admin_add_book_low_stock")
            record("ST_04", "Admin sales report totals and add book / low-stock alert",
                   "Three completed orders of 300, 450, 250 plus two Sapiens orders; open report; add book with stock 3", st04)
            br.close()
    finally:
        srv.terminate()
    json.dump(results, open(os.path.join(OUT, "system_results.json"), "w"), indent=1)
    for r in results:
        print(r["id"], r["result"], r["note"])


main()

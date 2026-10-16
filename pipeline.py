import sqlite3
import sys
from contextlib import closing

from extract_invoice import Invoice, extract_invoice

DB = "invoices.db"
TOLERANCE = 0.5


def check_totals(inv: Invoice) -> Invoice:
    """কোড দিয়ে যোগফল মেলায়। না মিললে flags-এ total_mismatch যোগ করে।"""
    if inv.total is None or not inv.line_items:
        return inv
    computed = round(sum(i.quantity * i.unit_price for i in inv.line_items), 2)
    problem = False
    if inv.subtotal is not None and abs(computed - inv.subtotal) > TOLERANCE:
        problem = True
    base = inv.subtotal if inv.subtotal is not None else computed
    expected_total = base - (inv.discount or 0) + (inv.vat_amount or 0)
    if abs(expected_total - inv.total) > TOLERANCE:
        problem = True
    if problem and "total_mismatch" not in inv.flags:
        inv.flags.append("total_mismatch")
    return inv


def init_db(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT, invoice_number TEXT, date TEXT, vendor TEXT,
            customer TEXT, currency TEXT, total REAL, flags TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS line_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER REFERENCES invoices(id),
            description TEXT, quantity REAL, unit_price REAL
        );
        """
    )


def save_invoice(inv: Invoice, source_file: str, db_path: str = DB):
    """SQLite-এ সেভ করে। ইনভয়েস নয় এমন ডকুমেন্ট সেভ হয় না।"""
    if "not_invoice" in inv.flags:
        return None
    with closing(sqlite3.connect(db_path)) as conn:
        init_db(conn)
        cur = conn.execute(
            "INSERT INTO invoices (source_file, invoice_number, date, vendor, customer,"
            " currency, total, flags) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (source_file, inv.invoice_number, inv.date, inv.vendor, inv.customer,
             inv.currency, inv.total, ",".join(inv.flags)),
        )
        invoice_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO line_items (invoice_id, description, quantity, unit_price)"
            " VALUES (?, ?, ?, ?)",
            [(invoice_id, i.description, i.quantity, i.unit_price) for i in inv.line_items],
        )
        conn.commit()
    return invoice_id


def process(path: str) -> Invoice:
    return check_totals(extract_invoice(path))


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "dev/inv_01.pdf"
    inv = process(path)
    print(inv.model_dump_json(indent=2))
    print("সেভ হয়েছে, id =", save_invoice(inv, path))	
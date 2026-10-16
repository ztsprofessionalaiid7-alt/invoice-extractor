import sqlite3

from extract_invoice import Invoice, LineItem
from pipeline import check_totals, save_invoice


def make(total, subtotal=None, discount=None, vat_amount=None, flags=None):
    return Invoice(
        invoice_number="T-1", date="2026-01-15", vendor="V", customer="C",
        currency="BDT", subtotal=subtotal, discount=discount, vat_amount=vat_amount,
        total=total,
        line_items=[LineItem(description="A", quantity=2, unit_price=100),
                    LineItem(description="B", quantity=1, unit_price=50)],
        flags=flags or [],
    )


def test_correct_total_has_no_flag():
    assert "total_mismatch" not in check_totals(make(total=250)).flags


def test_wrong_total_is_flagged():
    assert "total_mismatch" in check_totals(make(total=300)).flags


def test_discount_and_vat_are_handled():
    inv = make(total=210, subtotal=250, discount=50, vat_amount=10)
    assert "total_mismatch" not in check_totals(inv).flags


def test_wrong_total_with_discount_is_flagged():
    inv = make(total=999, subtotal=250, discount=50, vat_amount=10)
    assert "total_mismatch" in check_totals(inv).flags


def test_save_writes_invoice_and_items(tmp_path):
    db = str(tmp_path / "t.db")
    new_id = save_invoice(make(total=250), "x.pdf", db_path=db)
    conn = sqlite3.connect(db)
    assert new_id == 1
    assert conn.execute("select count(*) from invoices").fetchone()[0] == 1
    assert conn.execute("select count(*) from line_items").fetchone()[0] == 2
    conn.close()


def test_not_invoice_is_not_saved(tmp_path):
    db = str(tmp_path / "t.db")
    inv = make(total=None, flags=["not_invoice"])
    assert save_invoice(inv, "letter.pdf", db_path=db) is None
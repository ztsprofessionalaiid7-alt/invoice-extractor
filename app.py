import hashlib
import os
import sqlite3
import tempfile
from contextlib import closing

import pandas as pd
import streamlit as st

from extract_invoice import Invoice
from pipeline import DB, init_db, process, save_invoice

MAX_MB = 2
MAX_USES = 5
SHOW_SAVED = os.environ.get("SHOW_SAVED") == "1"
SAMPLE = "dev/inv_01.pdf"

FLAG_TEXT = {
    "total_mismatch": "সতর্কতা: আইটেমের যোগফল আর ছাপা মোট মিলছে না।",
    "ambiguous_date": "সতর্কতা: তারিখের দিন/মাস ক্রম অস্পষ্ট, তাই তারিখ খালি রাখা হয়েছে।",
    "prompt_injection": "সতর্কতা: ডকুমেন্টে এআই-কে নির্দেশ দেওয়ার চেষ্টা পাওয়া গেছে, ওগুলো উপেক্ষা করা হয়েছে।",
}

st.set_page_config(page_title="Invoice Extractor", page_icon="🧾")
st.title("🧾 Invoice Extractor")
st.caption(
    "PDF ইনভয়েস আপলোড করলে কাঠামোবদ্ধ ডেটা পাবেন। "
    "এই ডেমোর নমুনা ইনভয়েসগুলো বানানো (synthetic)। আপনার ফাইল সংরক্ষণ করা হয় না।"
)

if os.path.exists(SAMPLE):
    with open(SAMPLE, "rb") as f:
        st.download_button(
            "নমুনা ইনভয়েস ডাউনলোড করুন",
            f.read(),
            file_name="sample_invoice.pdf",
            mime="application/pdf",
        )


@st.cache_data(show_spinner=False)
def run(file_bytes: bytes) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        path = tmp.name
    try:
        return process(path).model_dump()
    finally:
        os.remove(path)


uploaded = st.file_uploader("PDF ফাইল বেছে নিন", type=["pdf"])

if uploaded is not None:
    data = uploaded.getvalue()
    digest = hashlib.md5(data).hexdigest()
    seen = st.session_state.setdefault("seen", set())
    result = None
    if len(data) > MAX_MB * 1024 * 1024:
        st.error(f"ফাইল {MAX_MB} MB-এর বেশি হতে পারবে না।")
    elif digest not in seen and len(seen) >= MAX_USES:
        st.error(f"ডেমোতে একবারে সর্বোচ্চ {MAX_USES}টা ফাইল চালানো যায়। পেজ রিফ্রেশ করে আবার চেষ্টা করুন।")
    else:
        with st.spinner("পড়া হচ্ছে..."):
            try:
                result = run(data)
                seen.add(digest)
            except Exception:
                st.error("এই মুহূর্তে প্রসেস করা যায়নি। একটু পরে আবার চেষ্টা করুন।")
    if result is not None:
        inv = Invoice(**result)
        if "not_invoice" in inv.flags:
            st.warning("এটা ইনভয়েস বলে মনে হচ্ছে না।")
        else:
            for f in inv.flags:
                st.warning(FLAG_TEXT.get(f, f))
            c1, c2, c3 = st.columns(3)
            c1.metric("ইনভয়েস নম্বর", inv.invoice_number or "-")
            c2.metric("তারিখ", inv.date or "-")
            total_text = f"{inv.total:,.2f} {inv.currency or ''}" if inv.total is not None else "-"
            c3.metric("মোট", total_text)
            st.write(f"**বিক্রেতা:** {inv.vendor or '-'}  |  **গ্রাহক:** {inv.customer or '-'}")
            df = pd.DataFrame([i.model_dump() for i in inv.line_items])
            if not df.empty:
                df["amount"] = df["quantity"] * df["unit_price"]
            st.dataframe(df)
            with st.expander("JSON আউটপুট"):
                st.json(result)
            if SHOW_SAVED and st.button("ডেটাবেসে সেভ করুন"):
                new_id = save_invoice(inv, uploaded.name)
                st.success(f"সেভ হয়েছে (id {new_id})")

if SHOW_SAVED:
    st.divider()
    st.subheader("সেভ করা ইনভয়েস")
    with closing(sqlite3.connect(DB)) as conn:
        init_db(conn)
        rows = pd.read_sql_query(
            "SELECT id, invoice_number, date, vendor, total, flags FROM invoices"
            " ORDER BY id DESC LIMIT 20",
            conn,
        )
    st.dataframe(rows)
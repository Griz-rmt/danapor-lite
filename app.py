import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime

# --- DATABASE SETUP ---
def get_connection():
    conn = sqlite3.connect("keuangan_lokal.db")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transaksi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal TEXT,
            jenis TEXT,
            kategori TEXT,
            nominal INTEGER,
            catatan TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- UI STREAMLIT ---
st.title("Pencatat Keuangan Lokal")

# Form Input
with st.form("form_transaksi", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        tanggal = st.date_input("Tanggal", datetime.now())
        jenis = st.selectbox("Jenis", ["Pengeluaran", "Pemasukan"])
    with col2:
        kategori = st.selectbox("Kategori", ["Makanan", "Transportasi", "Gaji", "Belanja", "Tagihan", "Lainnya"])
        nominal = st.number_input("Nominal (Rp)", min_value=0, step=1000)
    
    catatan = st.text_input("Catatan")
    submit = st.form_submit_button("Simpan Transaksi")

# Simpan ke SQLite
if submit:
    if nominal > 0:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO transaksi (tanggal, jenis, kategori, nominal, catatan) VALUES (?, ?, ?, ?, ?)",
            (str(tanggal), jenis, kategori, nominal, catatan)
        )
        conn.commit()
        conn.close()
        st.success("Data berhasil disimpan ke database!")
        st.rerun()
    else:
        st.warning("Nominal harus lebih besar dari 0.")

# --- TAMPILAN DATA & RINGKASAN ---
conn = get_connection()
df = pd.read_sql_query("SELECT * FROM transaksi ORDER BY id DESC", conn)
conn.close()

if not df.empty:
    st.subheader("Ringkasan Total")
    total_masuk = df[df['jenis'] == 'Pemasukan']['nominal'].sum()
    total_keluar = df[df['jenis'] == 'Pengeluaran']['nominal'].sum()
    sisa = total_masuk - total_keluar

    m1, m2, m3 = st.columns(3)
    m1.metric("Pemasukan", f"Rp {total_masuk:,}")
    m2.metric("Pengeluaran", f"Rp {total_keluar:,}")
    m3.metric("Saldo Sisa", f"Rp {sisa:,}")

    st.subheader("Riwayat Transaksi")
    st.dataframe(df.drop(columns=['id']), use_container_width=True)

    # Grafik Pengeluaran
    df_pengeluaran = df[df['jenis'] == 'Pengeluaran']
    if not df_pengeluaran.empty:
        st.subheader("Pengeluaran per Kategori")
        chart_data = df_pengeluaran.groupby("Kategori")["nominal"].sum()
        st.bar_chart(chart_data)
else:
    st.info("Belum ada data tersimpan di database.")
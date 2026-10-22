import io
import json
import sqlite3
import calendar
import pandas as pd
import streamlit as st
from datetime import datetime
from PIL import Image
from google import genai

# =============================================================================
# KONFIGURASI
# =============================================================================
GEMINI_API_KEY = "AIzaSyC6PgrB4J_ZvUs7J6aX3qPVFDXKBcEtWsc"
client = genai.Client(api_key=GEMINI_API_KEY)

KATEGORI_PENGELUARAN = ["Makanan", "Belanja", "Transportasi", "Tagihan", "Lainnya"]
KATEGORI_PEMASUKAN   = ["Gaji", "Freelance", "Investasi", "Lainnya"]

# =============================================================================
# DATABASE
# =============================================================================
DB_PATH = "keuangan_lokal.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transaksi (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                tanggal  TEXT    NOT NULL,
                jenis    TEXT    NOT NULL,
                kategori TEXT    NOT NULL,
                nominal  INTEGER NOT NULL,
                catatan  TEXT
            )
        """)
        conn.commit()

init_db()

def insert_transaksi(tanggal, jenis, kategori, nominal, catatan):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO transaksi (tanggal, jenis, kategori, nominal, catatan) VALUES (?, ?, ?, ?, ?)",
            (str(tanggal), jenis, kategori, int(nominal), catatan)
        )
        conn.commit()

def delete_transaksi(row_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM transaksi WHERE id = ?", (row_id,))
        conn.commit()

def load_all() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT id, tanggal, jenis, kategori, nominal, catatan FROM transaksi ORDER BY tanggal DESC, id DESC",
            conn
        )
    return df

# =============================================================================
# GEMINI – SCAN STRUK
# =============================================================================
def scan_struk(image_bytes: bytes) -> dict:
    prompt = """
Analisis gambar struk belanja ini dan ekstrak datanya ke format JSON murni tanpa markdown atau formatting tambahan:
{
    "tanggal": "YYYY-MM-DD",
    "kategori": "Makanan" | "Belanja" | "Transportasi" | "Tagihan" | "Lainnya",
    "nominal": 125000,
    "catatan": "Nama Toko / Ringkasan Singkat"
}
Aturan:
1. Ambil nilai TOTAL AKHIR / GRAND TOTAL yang dibayar.
2. Jika tanggal tidak terbaca, gunakan tanggal hari ini.
3. Output HANYA JSON valid, tanpa penjelasan apapun.
"""
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[Image.open(io.BytesIO(image_bytes)), prompt]
    )
    clean = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)

# =============================================================================
# HELPERS UI
# =============================================================================
def fmt_rupiah(val: int) -> str:
    return f"Rp {val:,.0f}".replace(",", ".")

BULAN_ID = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

# =============================================================================
# LAYOUT UTAMA
# =============================================================================
st.set_page_config(page_title="Danapor – Catatan Keuangan", page_icon="💰", layout="centered")
st.title("💰 Danapor")
st.caption("Aplikasi pencatat keuangan pribadi")

tab_catat, tab_struk, tab_riwayat = st.tabs([
    "✍️  Pencatatan",
    "📷  Scan Struk",
    "📊  Riwayat",
])

# =============================================================================
# TAB 1 – PENCATATAN MANUAL
# =============================================================================
with tab_catat:
    st.subheader("Tambah Transaksi Baru")

    jenis_input = st.radio("Jenis Transaksi", ["Pengeluaran", "Pemasukan"], horizontal=True, key="jenis_radio")

    with st.form("form_manual", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            tgl   = st.date_input("Tanggal", datetime.now().date())
            nom   = st.number_input("Nominal (Rp)", min_value=0, step=1_000, format="%d")
        with col2:
            opsi_kat = KATEGORI_PENGELUARAN if jenis_input == "Pengeluaran" else KATEGORI_PEMASUKAN
            kat   = st.selectbox("Kategori", opsi_kat)
            cat   = st.text_input("Catatan (opsional)")

        simpan = st.form_submit_button("💾  Simpan", use_container_width=True, type="primary")

    if simpan:
        if nom <= 0:
            st.warning("Nominal harus lebih dari 0.")
        else:
            insert_transaksi(tgl, jenis_input, kat, nom, cat)
            st.success(f"Transaksi {jenis_input.lower()} sebesar **{fmt_rupiah(nom)}** berhasil disimpan.")
            st.rerun()

# =============================================================================
# TAB 2 – SCAN STRUK
# =============================================================================
with tab_struk:
    st.subheader("Scan Struk Belanja")
    st.caption("Foto struk akan dibaca otomatis oleh AI. Kamu bisa koreksi hasilnya sebelum disimpan.")

    kamera_file = st.camera_input("📸  Arahkan kamera ke struk")

    if kamera_file:
        with st.spinner("Membaca struk dengan Gemini AI…"):
            try:
                hasil = scan_struk(kamera_file.getvalue())
                st.success("Struk berhasil dibaca! Periksa dan koreksi data di bawah sebelum menyimpan.")
            except Exception as e:
                st.error(f"Gagal membaca struk: {e}")
                hasil = None

        if hasil:
            st.divider()
            st.markdown("#### ✏️ Koreksi Data Struk")
            st.info("Semua field bisa diubah jika AI salah membaca.", icon="ℹ️")

            with st.form("form_struk"):
                col1, col2 = st.columns(2)
                with col1:
                    # parse tanggal – fallback ke hari ini jika gagal
                    try:
                        tgl_default = datetime.strptime(hasil.get("tanggal", ""), "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        tgl_default = datetime.now().date()

                    tgl_struk = st.date_input("Tanggal", tgl_default)
                    nom_struk = st.number_input(
                        "Nominal Total (Rp)",
                        value=int(hasil.get("nominal", 0)),
                        min_value=0,
                        step=1_000,
                        format="%d"
                    )
                with col2:
                    kat_default = hasil.get("kategori", "Lainnya")
                    kat_index   = KATEGORI_PENGELUARAN.index(kat_default) if kat_default in KATEGORI_PENGELUARAN else len(KATEGORI_PENGELUARAN) - 1
                    kat_struk   = st.selectbox("Kategori", KATEGORI_PENGELUARAN, index=kat_index)
                    cat_struk   = st.text_input("Catatan / Nama Toko", value=hasil.get("catatan", ""))

                simpan_struk = st.form_submit_button("💾  Simpan ke Riwayat", use_container_width=True, type="primary")

            if simpan_struk:
                if nom_struk <= 0:
                    st.warning("Nominal harus lebih dari 0.")
                else:
                    insert_transaksi(tgl_struk, "Pengeluaran", kat_struk, nom_struk, cat_struk)
                    st.success(f"Transaksi dari struk sebesar **{fmt_rupiah(nom_struk)}** berhasil disimpan.")
                    st.rerun()

# =============================================================================
# TAB 3 – RIWAYAT
# =============================================================================
with tab_riwayat:
    st.subheader("Riwayat Transaksi")

    df_all = load_all()

    if df_all.empty:
        st.info("Belum ada transaksi. Tambahkan di tab Pencatatan atau Scan Struk.")
    else:
        df_all["tanggal"] = pd.to_datetime(df_all["tanggal"])
        df_all["bulan"]   = df_all["tanggal"].dt.month
        df_all["tahun"]   = df_all["tanggal"].dt.year

        # --- Filter bulan & tahun ---
        tahun_tersedia = sorted(df_all["tahun"].unique(), reverse=True)
        now = datetime.now()

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            tahun_pilih = st.selectbox("Tahun", tahun_tersedia, index=0)
        with col_f2:
            bulan_tersedia = sorted(df_all[df_all["tahun"] == tahun_pilih]["bulan"].unique())
            bulan_label    = {b: BULAN_ID[b] for b in bulan_tersedia}
            # default ke bulan sekarang jika tersedia, jika tidak ambil yang terakhir
            default_bulan  = now.month if now.month in bulan_tersedia else bulan_tersedia[-1]
            bulan_pilih    = st.selectbox(
                "Bulan",
                options=list(bulan_label.keys()),
                format_func=lambda x: bulan_label[x],
                index=list(bulan_label.keys()).index(default_bulan)
            )

        df = df_all[(df_all["tahun"] == tahun_pilih) & (df_all["bulan"] == bulan_pilih)].copy()

        periode_label = f"{BULAN_ID[bulan_pilih]} {tahun_pilih}"
        st.markdown(f"##### 📅 {periode_label}")

        if df.empty:
            st.info(f"Tidak ada transaksi di {periode_label}.")
        else:
            # --- Summary saldo ---
            total_masuk  = df[df["jenis"] == "Pemasukan"]["nominal"].sum()
            total_keluar = df[df["jenis"] == "Pengeluaran"]["nominal"].sum()
            saldo        = total_masuk - total_keluar

            c1, c2, c3 = st.columns(3)
            c1.metric("Pemasukan",   fmt_rupiah(total_masuk))
            c2.metric("Pengeluaran", fmt_rupiah(total_keluar))
            c3.metric("Saldo Bulan", fmt_rupiah(saldo), delta=fmt_rupiah(saldo) if saldo != 0 else None)

            st.divider()

            # --- Tabel transaksi ---
            st.markdown("**Detail Transaksi**")

            df_tampil = df[["tanggal", "jenis", "kategori", "nominal", "catatan"]].copy()
            df_tampil["tanggal"] = df_tampil["tanggal"].dt.strftime("%d %b %Y")
            df_tampil["nominal"] = df_tampil["nominal"].apply(fmt_rupiah)
            df_tampil.columns    = ["Tanggal", "Jenis", "Kategori", "Nominal", "Catatan"]

            st.dataframe(df_tampil, use_container_width=True, hide_index=True)

            # Hapus transaksi
            with st.expander("🗑️  Hapus Transaksi"):
                id_list = df[["id", "tanggal", "kategori", "nominal"]].copy()
                id_list["label"] = id_list.apply(
                    lambda r: f"#{r['id']}  |  {r['tanggal'].strftime('%d %b')}  |  {r['kategori']}  |  {fmt_rupiah(r['nominal'])}",
                    axis=1
                )
                pilih = st.selectbox("Pilih transaksi yang akan dihapus", id_list["label"].tolist())
                row_id = int(id_list[id_list["label"] == pilih]["id"].values[0])
                if st.button("Hapus", type="primary"):
                    delete_transaksi(row_id)
                    st.success("Transaksi dihapus.")
                    st.rerun()

            st.divider()

            # --- Grafik pengeluaran per kategori ---
            df_keluar = df[df["jenis"] == "Pengeluaran"]
            if not df_keluar.empty:
                st.markdown("**Pengeluaran per Kategori**")
                chart_data = df_keluar.groupby("kategori")["nominal"].sum().sort_values(ascending=False)
                st.bar_chart(chart_data)

            # --- Grafik tren harian ---
            st.markdown("**Tren Harian**")
            tren = df.groupby(["tanggal", "jenis"])["nominal"].sum().unstack(fill_value=0).reset_index()
            tren["tanggal"] = tren["tanggal"].dt.strftime("%d")
            tren = tren.set_index("tanggal")
            st.bar_chart(tren)

import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime

# =============================================================================
# KONFIGURASI
# =============================================================================
KATEGORI_PENGELUARAN = ["Makanan", "Belanja", "Transportasi", "Tagihan", "Lainnya..."]
KATEGORI_PEMASUKAN   = ["Gaji", "Freelance", "Investasi", "Lainnya..."]

# =============================================================================
# HALAMAN LOGIN
# =============================================================================
st.set_page_config(page_title="Danapor – Catatan Keuangan", page_icon="💰", layout="centered")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("💰 Danapor")
    st.subheader("Masukkan kode akses")

    with st.form("form_login"):
        kode  = st.text_input("Kode Akses", type="password", placeholder="••••••••")
        masuk = st.form_submit_button("Masuk", use_container_width=True, type="primary")

    if masuk:
        if kode == st.secrets["pass-code"]:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Kode akses salah.")

    st.stop()

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

def delete_transaksi(row_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM transaksi WHERE id = ?", (row_id,))
        conn.commit()

def load_all() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT id, tanggal, jenis, kategori, nominal, catatan "
            "FROM transaksi ORDER BY tanggal DESC, id DESC",
            conn
        )
    return df

# =============================================================================
# HELPERS
# =============================================================================
def fmt_rupiah(val: int) -> str:
    return f"Rp {val:,.0f}".replace(",", ".")

BULAN_ID = {
    1: "Januari",   2: "Februari", 3: "Maret",    4: "April",
    5: "Mei",       6: "Juni",     7: "Juli",      8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}

# =============================================================================
# LAYOUT UTAMA
# =============================================================================
col_title, col_logout = st.columns([5, 1])
with col_title:
    st.title("💰 Danapor")
    st.caption("Aplikasi pencatat keuangan pribadi")
with col_logout:
    st.write("")
    if st.button("Keluar", use_container_width=True):
        st.session_state.logged_in = False
        st.rerun()

tab_catat, tab_riwayat = st.tabs(["✍️  Pencatatan", "📊  Riwayat"])

# =============================================================================
# TAB 1 – PENCATATAN
# =============================================================================
with tab_catat:
    st.subheader("Tambah Transaksi Baru")

    jenis_input = st.radio(
        "Jenis Transaksi", ["Pengeluaran", "Pemasukan"],
        horizontal=True, key="jenis_radio"
    )

    opsi_kat = KATEGORI_PENGELUARAN if jenis_input == "Pengeluaran" else KATEGORI_PEMASUKAN

    # Selectbox & field custom kategori di LUAR form agar langsung reaktif
    col_kat1, col_kat2 = st.columns(2)
    with col_kat1:
        kat_pilih = st.selectbox("Kategori", opsi_kat, key="kat_pilih")
    with col_kat2:
        if kat_pilih == "Lainnya...":
            kat_custom = st.text_input("Tulis kategori", placeholder="contoh: Kesehatan, Hobi…", key="kat_custom")
        else:
            kat_custom = ""
            st.empty()  # jaga layout tetap simetris

    with st.form("form_manual", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            tgl = st.date_input("Tanggal", datetime.now().date())
            nom = st.number_input("Nominal (Rp)", min_value=0, step=1_000, format="%d")
        with col2:
            # Tampilkan info kategori yang sudah dipilih di atas (read-only di dalam form)
            kat_display = kat_custom.strip() if kat_pilih == "Lainnya..." else kat_pilih
            st.text_input("Kategori dipilih", value=kat_display, disabled=True)

        cat = st.text_area(
            "Catatan / Deskripsi",
            placeholder="Tulis keterangan selengkap-lengkapnya…",
            height=120
        )

        simpan = st.form_submit_button("💾  Simpan", use_container_width=True, type="primary")

    if simpan:
        kat_final = kat_custom.strip() if kat_pilih == "Lainnya..." else kat_pilih
        if nom <= 0:
            st.warning("Nominal harus lebih dari 0.")
        elif kat_pilih == "Lainnya..." and not kat_final:
            st.warning("Tulis nama kategori terlebih dahulu.")
        else:
            insert_transaksi(tgl, jenis_input, kat_final, nom, cat.strip())
            st.success(
                f"Transaksi **{jenis_input.lower()}** sebesar **{fmt_rupiah(nom)}** "
                f"— {kat_final} berhasil disimpan."
            )

# =============================================================================
# TAB 2 – RIWAYAT
# =============================================================================
with tab_riwayat:
    st.subheader("Riwayat Transaksi")

    df_all = load_all()

    if df_all.empty:
        st.info("Belum ada transaksi. Tambahkan di tab Pencatatan.")
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
            default_bulan  = now.month if now.month in bulan_tersedia else bulan_tersedia[-1]
            bulan_pilih    = st.selectbox(
                "Bulan",
                options=list(bulan_label.keys()),
                format_func=lambda x: bulan_label[x],
                index=list(bulan_label.keys()).index(default_bulan)
            )

        df = df_all[
            (df_all["tahun"] == tahun_pilih) &
            (df_all["bulan"] == bulan_pilih)
        ].copy()

        periode_label = f"{BULAN_ID[bulan_pilih]} {tahun_pilih}"
        st.markdown(f"##### 📅 {periode_label}")

        if df.empty:
            st.info(f"Tidak ada transaksi di {periode_label}.")
        else:
            # --- Summary saldo ---
            total_masuk  = int(df[df["jenis"] == "Pemasukan"]["nominal"].sum())
            total_keluar = int(df[df["jenis"] == "Pengeluaran"]["nominal"].sum())
            saldo        = total_masuk - total_keluar

            c1, c2, c3 = st.columns(3)
            c1.metric("🟢 Pemasukan",   fmt_rupiah(total_masuk))
            c2.metric("🔴 Pengeluaran", fmt_rupiah(total_keluar))
            if saldo > 0:
                c3.metric("Saldo Bulan", fmt_rupiah(saldo),
                          delta=f"+ {fmt_rupiah(saldo)}", delta_color="normal")
            elif saldo < 0:
                c3.metric("Saldo Bulan", fmt_rupiah(saldo),
                          delta=f"- {fmt_rupiah(abs(saldo))}", delta_color="inverse")
            else:
                c3.metric("Saldo Bulan", fmt_rupiah(saldo), delta="Impas", delta_color="off")

            st.divider()

            # --- Daftar transaksi dengan expander detail ---
            st.markdown("**Detail Transaksi** — klik untuk melihat catatan lengkap")

            for _, row in df.iterrows():
                tgl_str = row["tanggal"].strftime("%d %b %Y")
                icon    = "🟢" if row["jenis"] == "Pemasukan" else "🔴"
                label   = f"{icon} {tgl_str}  |  {row['kategori']}  |  {fmt_rupiah(row['nominal'])}"

                with st.expander(label):
                    col_a, col_b = st.columns(2)
                    col_a.markdown(f"**Jenis:** {row['jenis']}")
                    col_a.markdown(f"**Kategori:** {row['kategori']}")
                    col_b.markdown(f"**Tanggal:** {tgl_str}")
                    col_b.markdown(f"**Nominal:** {fmt_rupiah(row['nominal'])}")

                    st.markdown("**Catatan:**")
                    st.write(row["catatan"] if row["catatan"] else "_tidak ada catatan_")

                    st.divider()
                    if st.button("🗑️ Hapus transaksi ini", key=f"hapus_{row['id']}", type="primary"):
                        delete_transaksi(int(row["id"]))
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

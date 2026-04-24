import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Ev Bütçesi ve Borç Takibi", layout="wide")

@st.cache_data
def load_gider_data():
    """
    gider.csv dosyasını okur.
    Dosya yapısı:
    - Satır 1-16: ihtiyaç kredisi tablosu (ayraç: ;, 11 sütun)
    - Satır 18-27: khm kredisi tablosu
    - Satır 30-38: kredi kartı tablosu
    - Satır 40-49: münferit tablo (aylar + aylık borç)
    """
    # Tüm dosyayı ham oku
    df_raw = pd.read_csv("gider.csv", sep=";", header=None, engine="python", on_bad_lines="skip")

    # --- İHTİYAÇ KREDİSİ TABLOSU ---
    # Başlık satırı: sırala, tarih, banka, aylık borç, ödeme günü, taksit sayısı, toplam borç, şuank borç, faiz, fark, bitiş tarihi
    ihtiyac_cols = ["sıra", "tarih_sıra", "banka", "aylık_borç", "ödeme_günü", "taksit_sayısı", "toplam_borç", "şuank_borç", "faiz", "fark", "bitiş_tarihi"]
    
    # Veri satırları: 2. satırdan (index 2) boş satıra kadar (index 16)
    df_ihtiyac = df_raw.iloc[2:16].copy()
    df_ihtiyac.columns = ihtiyac_cols
    df_ihtiyac = df_ihtiyac[df_ihtiyac["sıra"].notna() & (df_ihtiyac["sıra"] != "")]
    
    for col in ["aylık_borç", "şuank_borç", "toplam_borç"]:
        df_ihtiyac[col] = (
            df_ihtiyac[col]
            .astype(str)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .pipe(pd.to_numeric, errors="coerce")
            .fillna(0)
        )

    # --- KHM KREDİSİ TABLOSU ---
    # Satır 18 başlık, 19-26 veri
    khm_cols = ["banka", "toplam_borç", "kalan_limit", "aylık_borç", "ekstra", "x1", "x2", "x3", "x4", "x5", "x6"]
    df_khm = df_raw.iloc[19:27].copy()
    df_khm = df_khm.iloc[:, :4]
    df_khm.columns = ["banka", "toplam_borç", "kalan_limit", "aylık_borç"]
    df_khm = df_khm[df_khm["banka"].notna() & (df_khm["banka"] != "")]
    
    for col in ["aylık_borç", "toplam_borç"]:
        df_khm[col] = (
            df_khm[col]
            .astype(str)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .pipe(pd.to_numeric, errors="coerce")
            .fillna(0)
        )

    # --- KREDİ KARTI TABLOSU ---
    # Satır 30 başlık, 31-37 veri
    df_kk = df_raw.iloc[31:38].copy()
    df_kk = df_kk.iloc[:, :6]
    df_kk.columns = ["banka", "toplam_borç", "kalan_limit", "aylık_borç", "hesap_kesim", "ödeme_günü"]
    df_kk = df_kk[df_kk["banka"].notna() & (df_kk["banka"].astype(str).str.strip() != "")]
    
    for col in ["aylık_borç", "toplam_borç"]:
        df_kk[col] = (
            df_kk[col]
            .astype(str)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .pipe(pd.to_numeric, errors="coerce")
            .fillna(0)
        )

    # --- MÜNFERİT TABLO (Gelir) ---
    # Satır 40 başlık, 41-48 veri
    df_munferit = df_raw.iloc[41:49].copy()
    df_munferit = df_munferit.iloc[:, :2]
    df_munferit.columns = ["ay", "aylık_borç"]
    df_munferit = df_munferit[df_munferit["ay"].notna() & (df_munferit["ay"] != "")]
    df_munferit["aylık_borç"] = (
        df_munferit["aylık_borç"]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    return df_ihtiyac, df_khm, df_kk, df_munferit


@st.cache_data
def load_gelir_data():
    """gelir.csv dosyasını okur — aynı yapıda ise gider ile aynı parse edilir"""
    try:
        df_raw = pd.read_csv("gelir.csv", sep=";", header=None, engine="python", on_bad_lines="skip")
        # Münferit tabloyu bul (AYLAR sütunu olan satır)
        mask = df_raw.apply(lambda row: row.astype(str).str.contains("mayıs|haziran|temmuz", case=False, na=False).any(), axis=1)
        start = mask[mask].index[0]
        
        df_gelir = df_raw.iloc[start:start+8].copy()
        df_gelir = df_gelir.iloc[:, :2]
        df_gelir.columns = ["ay", "tutar"]
        df_gelir["tutar"] = (
            df_gelir["tutar"]
            .astype(str)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .pipe(pd.to_numeric, errors="coerce")
            .fillna(0)
        )
        return df_gelir
    except Exception:
        return None


# ===================== ANA UYGULAMA =====================

try:
    df_ihtiyac, df_khm, df_kk, df_munferit = load_gider_data()

    st.title("🏠 Ev Bütçesi ve Borç Takibi")
    st.markdown("---")

    # ---- ÖZET METRİKLER ----
    toplam_ihtiyac_taksit = df_ihtiyac["aylık_borç"].sum()
    toplam_ihtiyac_borc = df_ihtiyac["şuank_borç"].sum()
    toplam_khm_taksit = df_khm["aylık_borç"].sum()
    toplam_kk_taksit = df_kk["aylık_borç"].sum()
    toplam_kk_borc = df_kk["toplam_borç"].sum()
    toplam_munferit = df_munferit["aylık_borç"].iloc[0] if len(df_munferit) > 0 else 0

    genel_aylik_taksit = toplam_ihtiyac_taksit + toplam_khm_taksit + toplam_kk_taksit
    genel_toplam_borc = toplam_ihtiyac_borc + toplam_kk_borc

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💳 Aylık Toplam Taksit", f"{genel_aylik_taksit:,.0f} ₺")
    col2.metric("📉 Toplam Kalan Borç", f"{genel_toplam_borc:,.0f} ₺")
    col3.metric("🏦 İhtiyaç Kredisi Taksit", f"{toplam_ihtiyac_taksit:,.0f} ₺")
    col4.metric("💰 KHM Aylık", f"{toplam_khm_taksit:,.0f} ₺")

    st.markdown("---")

    # ---- SEKMELİ GÖRÜNÜM ----
    tab1, tab2, tab3, tab4 = st.tabs(["📋 İhtiyaç Kredileri", "🏦 KHM Kredileri", "💳 Kredi Kartları", "📊 Genel Analiz"])

    with tab1:
        st.subheader("İhtiyaç Kredisi Detayları")
        show_df = df_ihtiyac[["banka", "aylık_borç", "şuank_borç", "taksit_sayısı", "faiz", "bitiş_tarihi"]].copy()
        show_df.columns = ["Banka", "Aylık Taksit (₺)", "Kalan Borç (₺)", "Kalan Taksit", "Faiz (%)", "Bitiş Tarihi"]
        st.dataframe(show_df, use_container_width=True, hide_index=True)

        fig = px.bar(
            df_ihtiyac.sort_values("aylık_borç", ascending=True),
            x="aylık_borç", y="banka", orientation="h",
            title="Bankaya Göre Aylık Taksit Tutarları",
            labels={"aylık_borç": "Aylık Taksit (₺)", "banka": "Banka"},
            color="aylık_borç", color_continuous_scale="Blues"
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("KHM (Kısa Vadeli) Kredi Detayları")
        show_khm = df_khm[["banka", "aylık_borç", "toplam_borç", "kalan_limit"]].copy()
        show_khm.columns = ["Banka", "Aylık Ödeme (₺)", "Toplam Borç (₺)", "Kalan Limit (₺)"]
        st.dataframe(show_khm, use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("Kredi Kartı Detayları")
        show_kk = df_kk[["banka", "aylık_borç", "toplam_borç", "kalan_limit", "ödeme_günü"]].copy()
        show_kk.columns = ["Banka", "Aylık Min. Ödeme (₺)", "Toplam Borç (₺)", "Kalan Limit (₺)", "Ödeme Günü"]
        st.dataframe(show_kk, use_container_width=True, hide_index=True)

        fig_kk = px.pie(
            df_kk[df_kk["toplam_borç"] > 0],
            names="banka", values="toplam_borç",
            title="Kredi Kartı Borç Dağılımı",
            hole=0.4
        )
        st.plotly_chart(fig_kk, use_container_width=True)

    with tab4:
        st.subheader("Genel Borç Analizi")

        # Münferit aylık gelir/gider karşılaştırması
        if len(df_munferit) > 0:
            st.markdown("#### 📅 Aylık Bütçe Durumu")
            ay_sec = st.selectbox("Ay Seçin", df_munferit["ay"].tolist())
            secilen_tutar = df_munferit[df_munferit["ay"] == ay_sec]["aylık_borç"].values[0]

            fig_bar = go.Figure(data=[
                go.Bar(name="Seçilen Ay Tutarı", x=["Münferit Tutar"], y=[secilen_tutar], marker_color="#636EFA"),
                go.Bar(name="Toplam Aylık Taksit", x=["Toplam Taksit"], y=[genel_aylik_taksit], marker_color="#EF553B"),
            ])
            fig_bar.update_layout(title=f"{ay_sec} – Münferit vs Toplam Taksit Karşılaştırması", barmode="group")
            st.plotly_chart(fig_bar, use_container_width=True)

        # Borç türlerine göre özet
        ozet_df = pd.DataFrame({
            "Borç Türü": ["İhtiyaç Kredisi", "Kredi Kartı"],
            "Toplam Borç (₺)": [toplam_ihtiyac_borc, toplam_kk_borc]
        })
        fig_ozet = px.pie(ozet_df, names="Borç Türü", values="Toplam Borç (₺)",
                          title="Toplam Borç Dağılımı", hole=0.35,
                          color_discrete_sequence=["#00CC96", "#EF553B"])
        st.plotly_chart(fig_ozet, use_container_width=True)

except Exception as e:
    st.error(f"Veri işlenirken hata oluştu: {e}")
    st.exception(e)

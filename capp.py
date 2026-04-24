import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

st.set_page_config(page_title="Ev Bütçesi ve Borç Takibi", layout="wide")

# ── Sabitler ─────────────────────────────────────────────────────────────────
AY_MAP = {
    "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4,
    "mayıs": 5, "haziran": 6, "temmuz": 7, "ağustos": 8,
    "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12,
}
AY_SIRA = ["mayıs", "haziran", "temmuz", "ağustos", "eylül", "ekim", "kasım", "aralık"]

def para_fmt(x: float) -> str:
    return f"{x:,.0f} ₺".replace(",", ".")

def temizle_sayi(seri):
    return (
        seri.astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

# ── Veri Yükleme ─────────────────────────────────────────────────────────────

@st.cache_data
def load_gider_data():
    df_raw = pd.read_csv("gider.csv", sep=";", header=None, engine="python", on_bad_lines="skip")

    def temizle(df, cols):
        for col in cols:
            df[col] = temizle_sayi(df[col])
        return df

    # İhtiyaç kredisi (satır 2-15)
    ihtiyac_cols = ["sıra", "tarih_sıra", "banka", "aylık_borç", "ödeme_günü",
                    "taksit_sayısı", "toplam_borç", "şuank_borç", "faiz", "fark", "bitiş_tarihi"]
    df_ihtiyac = df_raw.iloc[2:16].copy()
    df_ihtiyac.columns = ihtiyac_cols
    df_ihtiyac = df_ihtiyac[df_ihtiyac["sıra"].notna() & (df_ihtiyac["sıra"].astype(str).str.strip() != "")]
    df_ihtiyac = temizle(df_ihtiyac, ["aylık_borç", "şuank_borç", "toplam_borç"])

    # KHM (satır 19-26)
    df_khm = df_raw.iloc[19:27].copy().iloc[:, :4]
    df_khm.columns = ["banka", "toplam_borç", "kalan_limit", "aylık_borç"]
    df_khm = df_khm[df_khm["banka"].notna() & (df_khm["banka"].astype(str).str.strip() != "")]
    df_khm = temizle(df_khm, ["aylık_borç", "toplam_borç"])

    # Kredi kartı (satır 31-37)
    df_kk = df_raw.iloc[31:38].copy().iloc[:, :6]
    df_kk.columns = ["banka", "toplam_borç", "kalan_limit", "aylık_borç", "hesap_kesim", "ödeme_günü"]
    df_kk = df_kk[df_kk["banka"].notna() & (df_kk["banka"].astype(str).str.strip() != "")]
    df_kk = temizle(df_kk, ["aylık_borç", "toplam_borç"])

    # Münferit (satır 41-48) — aya göre sözlük
    df_munferit = df_raw.iloc[41:49].copy().iloc[:, :2]
    df_munferit.columns = ["ay", "aylık_borç"]
    df_munferit = df_munferit[df_munferit["ay"].notna() & (df_munferit["ay"].astype(str).str.strip() != "")]
    df_munferit["aylık_borç"] = temizle_sayi(df_munferit["aylık_borç"])
    df_munferit["ay"] = df_munferit["ay"].str.lower().str.strip()
    munferit_dict = dict(zip(df_munferit["ay"], df_munferit["aylık_borç"]))

    return df_ihtiyac, df_khm, df_kk, munferit_dict


@st.cache_data
def load_gelir_data():
    """
    gelir.csv yapısı:
      Satır 0: GELİR TABLOSU (başlık)
      Satır 1: ;öz;performans;çift;ek;temettü;kira;toplam GELİR
      Satır 2+: mayıs;140.000;...;175.000
    """
    df_raw = pd.read_csv("gelir.csv", sep=";", header=None, engine="python", on_bad_lines="skip")
    df = df_raw.iloc[2:].copy()
    df = df.iloc[:, [0, 7]]          # ay + toplam GELİR sütunları
    df.columns = ["ay", "toplam_gelir"]
    df["ay"] = df["ay"].astype(str).str.lower().str.strip()
    df = df[df["ay"].isin(AY_MAP.keys())]
    df["toplam_gelir"] = temizle_sayi(df["toplam_gelir"])
    return df


def bugun_ay_geliri(df_gelir: pd.DataFrame) -> tuple:
    """Bugünün ayını döndürür; Nisan → Mayıs gösterilir."""
    ay_no = date.today().month
    if ay_no == 4:
        ay_no = 5
    hedef = {v: k for k, v in AY_MAP.items()}.get(ay_no, "mayıs")
    row = df_gelir[df_gelir["ay"] == hedef]
    if not row.empty:
        return hedef.capitalize(), float(row.iloc[0]["toplam_gelir"])
    # Bulamazsa ilk satır
    return df_gelir.iloc[0]["ay"].capitalize(), float(df_gelir.iloc[0]["toplam_gelir"])


# ── Uygulama ─────────────────────────────────────────────────────────────────

try:
    df_ihtiyac, df_khm, df_kk, munferit_dict = load_gider_data()
    df_gelir = load_gelir_data()

    # Sabit taksit toplamları (aya göre değişmez)
    ihtiyac_taksit = df_ihtiyac["aylık_borç"].sum()
    ihtiyac_borc   = df_ihtiyac["şuank_borç"].sum()
    khm_taksit     = df_khm["aylık_borç"].sum()
    khm_borc       = df_khm["toplam_borç"].sum()
    kk_taksit      = df_kk["aylık_borç"].sum()
    kk_borc        = df_kk["toplam_borç"].sum()
    toplam_borc    = ihtiyac_borc + khm_borc + kk_borc

    ay_adi, ay_geliri = bugun_ay_geliri(df_gelir)
    ay_key = ay_adi.lower()
    munferit_bugun = munferit_dict.get(ay_key, 0)
    genel_taksit   = ihtiyac_taksit + khm_taksit + kk_taksit + munferit_bugun
    net_kalan      = ay_geliri - genel_taksit
    tarih_str      = date.today().strftime("%d.%m.%Y")

    # ── BAŞLIK ───────────────────────────────────────────────────────────
    bas_sol, bas_sag = st.columns([3, 1])
    with bas_sol:
        st.title("🏠 Ev Bütçesi ve Borç Takibi")
    with bas_sag:
        st.markdown(
            f"<div style='text-align:right;padding-top:22px;font-size:1.15rem;color:#aaa;'>"
            f"📅 {tarih_str}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── BORÇ DURUMU ───────────────────────────────────────────────────────
    st.markdown("#### 💳 Güncel Borç Durumu")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🏦 İhtiyaç Kredisi Borcu", para_fmt(ihtiyac_borc))
    c2.metric("📋 KHM Borcu",             para_fmt(khm_borc))
    c3.metric("💳 Kredi Kartı Borcu",      para_fmt(kk_borc))
    c4.metric("📉 Toplam Borç",            para_fmt(toplam_borc))

    st.markdown("---")

    # ── AYLIK NAKİT AKIŞI ────────────────────────────────────────────────
    st.markdown(f"#### 📊 {ay_adi} Ayı Nakit Akışı")
    d1, d2, d3, d4, d5, d6 = st.columns(6)
    d1.metric("🔴 İhtiyaç Taksit",  para_fmt(ihtiyac_taksit))
    d2.metric("🟠 KHM Taksit",      para_fmt(khm_taksit))
    d3.metric("🟡 KK Min. Ödeme",   para_fmt(kk_taksit))
    d4.metric("🟣 Münferit",         para_fmt(munferit_bugun))
    d5.metric("💵 Toplam Gelir",     para_fmt(ay_geliri))
    d6.metric(
        "✅ Net Kalan" if net_kalan >= 0 else "⚠️ Net Kalan",
        para_fmt(net_kalan),
    )

    st.markdown("---")

    # ── SEKMELİ DETAY ────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📋 İhtiyaç Kredileri", "🏦 KHM Kredileri", "💳 Kredi Kartları", "📊 Genel Analiz"]
    )

    with tab1:
        st.subheader("İhtiyaç Kredisi Detayları")
        show = df_ihtiyac[["banka", "aylık_borç", "şuank_borç", "taksit_sayısı", "faiz", "bitiş_tarihi"]].copy()
        show.columns = ["Banka", "Aylık Taksit (₺)", "Kalan Borç (₺)", "Kalan Taksit", "Faiz (%)", "Bitiş Tarihi"]
        st.dataframe(show, use_container_width=True, hide_index=True)
        fig1 = px.bar(
            df_ihtiyac.sort_values("aylık_borç", ascending=True),
            x="aylık_borç", y="banka", orientation="h",
            title="Bankaya Göre Aylık Taksit",
            labels={"aylık_borç": "Aylık Taksit (₺)", "banka": "Banka"},
            color="aylık_borç", color_continuous_scale="Blues",
        )
        st.plotly_chart(fig1, use_container_width=True)

    with tab2:
        st.subheader("KHM (Kısa Vadeli) Kredi Detayları")
        show_khm = df_khm[["banka", "aylık_borç", "toplam_borç", "kalan_limit"]].copy()
        show_khm.columns = ["Banka", "Aylık Ödeme (₺)", "Toplam Borç (₺)", "Kalan Limit (₺)"]
        st.dataframe(show_khm, use_container_width=True, hide_index=True)
        fig2 = px.bar(
            df_khm.sort_values("aylık_borç", ascending=True),
            x="aylık_borç", y="banka", orientation="h",
            title="KHM – Bankaya Göre Aylık Ödeme",
            labels={"aylık_borç": "Aylık Ödeme (₺)", "banka": "Banka"},
            color="aylık_borç", color_continuous_scale="Oranges",
        )
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        st.subheader("Kredi Kartı Detayları")
        show_kk = df_kk[["banka", "aylık_borç", "toplam_borç", "kalan_limit", "ödeme_günü"]].copy()
        show_kk.columns = ["Banka", "Min. Ödeme (₺)", "Toplam Borç (₺)", "Kalan Limit (₺)", "Ödeme Günü"]
        st.dataframe(show_kk, use_container_width=True, hide_index=True)
        fig3 = px.pie(
            df_kk[df_kk["toplam_borç"] > 0],
            names="banka", values="toplam_borç",
            title="Kredi Kartı Borç Dağılımı", hole=0.4,
        )
        st.plotly_chart(fig3, use_container_width=True)

    # ── GENEL ANALİZ ─────────────────────────────────────────────────────
    with tab4:
        st.subheader("Genel Borç Analizi")

        # Borç türü dağılımı (pasta)
        ozet_df = pd.DataFrame({
            "Borç Türü": ["İhtiyaç Kredisi", "KHM", "Kredi Kartı"],
            "Toplam Borç (₺)": [ihtiyac_borc, khm_borc, kk_borc],
        })
        fig_pie = px.pie(
            ozet_df, names="Borç Türü", values="Toplam Borç (₺)",
            title="Toplam Borç Dağılımı", hole=0.35,
            color_discrete_sequence=["#00CC96", "#FFA15A", "#EF553B"],
        )
        st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("---")

        # ── AYLIK GELİR / GİDER GRAFİĞİ ─────────────────────────────
        st.markdown("#### 📅 Aylık Gelir & Gider Karşılaştırması")
        st.caption("Gider = İhtiyaç taksit + KHM taksit + KK min. ödeme + o aya ait münferit")

        # Sadece gelir.csv'de olan ayları kullan, sırayı koru
        gelir_aylar = df_gelir["ay"].tolist()
        aylik_rows = []
        for ay in gelir_aylar:
            gelir_val = df_gelir.loc[df_gelir["ay"] == ay, "toplam_gelir"].values
            gelir_val = float(gelir_val[0]) if len(gelir_val) > 0 else 0
            munferit_val = munferit_dict.get(ay, 0)
            gider_val = ihtiyac_taksit + khm_taksit + kk_taksit + munferit_val
            aylik_rows.append({
                "Ay": ay.capitalize(),
                "Gelir": gelir_val,
                "Gider": gider_val,
                "Net": gelir_val - gider_val,
                "Münferit": munferit_val,
            })

        df_aylik = pd.DataFrame(aylik_rows)

        # Grup bar: Gelir vs Gider
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            name="Toplam Gelir",
            x=df_aylik["Ay"],
            y=df_aylik["Gelir"],
            marker_color="#00CC96",
            text=df_aylik["Gelir"].apply(lambda v: f"{v/1000:.0f}K"),
            textposition="outside",
        ))
        fig_bar.add_trace(go.Bar(
            name="Toplam Gider",
            x=df_aylik["Ay"],
            y=df_aylik["Gider"],
            marker_color="#EF553B",
            text=df_aylik["Gider"].apply(lambda v: f"{v/1000:.0f}K"),
            textposition="outside",
        ))
        fig_bar.update_layout(
            barmode="group",
            title="Aylık Gelir ve Gider",
            yaxis_title="Tutar (₺)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=420,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # Net kalan çizgi grafiği
        fig_net = go.Figure()
        fig_net.add_trace(go.Scatter(
            x=df_aylik["Ay"],
            y=df_aylik["Net"],
            mode="lines+markers+text",
            name="Net Kalan",
            line=dict(color="#636EFA", width=3),
            marker=dict(size=9),
            text=df_aylik["Net"].apply(lambda v: f"{v/1000:.0f}K ₺"),
            textposition="top center",
            fill="tozeroy",
            fillcolor="rgba(99,110,250,0.15)",
        ))
        fig_net.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig_net.update_layout(
            title="Aylık Net Kalan (Gelir − Gider)",
            yaxis_title="Net (₺)",
            height=350,
        )
        st.plotly_chart(fig_net, use_container_width=True)

        # Detay tablosu
        st.markdown("#### 📋 Aylık Detay Tablosu")
        tablo = df_aylik.copy()
        tablo["Gelir"]    = tablo["Gelir"].apply(para_fmt)
        tablo["Gider"]    = tablo["Gider"].apply(para_fmt)
        tablo["Net"]      = tablo["Net"].apply(para_fmt)
        tablo["Münferit"] = tablo["Münferit"].apply(para_fmt)
        tablo.columns     = ["Ay", "Toplam Gelir", "Toplam Gider", "Net Kalan", "Münferit"]
        st.dataframe(tablo, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Veri işlenirken hata oluştu: {e}")
    st.exception(e)

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import folium
from streamlit_folium import st_folium
import ee
from config import (GRUPOS, ASSETS, ANO_BASE, LOGO_WWF, CORES)
from utils.gee_loader import (
    init_gee, get_latest_date, get_tocantins_names,
    get_tocantins_display_names, get_monthly_temperature,
    get_monthly_temperature_hybrid, get_daily_temperature_current_month,
    get_temp_latest_day,
    get_temp_stats, get_focos_count_periodo, get_feature,
    get_all_lakes_temp_acumulado, get_monthly_focos
)
from utils.charts import (colorir_temp, colorir_dif, colorir_focos,
    grafico_temperatura_diaria, grafico_temperatura_mensal_hibrido)

st.set_page_config(
    page_title="Analises e Estatisticas — Lagos Amazonicos",
    page_icon=LOGO_WWF if LOGO_WWF else "📊",
    layout="wide"
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@600;700;800&family=Nunito:wght@400;500;600;700&display=swap');
  :root {
    --bg:#FDFCF8; --fg:#2C2C24; --primary:#5D7052; --primary-f:#F3F4F1;
    --secondary:#C18C5D; --accent:#E6DCCD; --muted:#F0EBE5;
    --muted-f:#78786C; --border:#DED8CF; --destructive:#A85448;
    --shadow-moss:0 4px 20px -2px rgba(93,112,82,0.15);
    --shadow-clay:0 10px 40px -10px rgba(193,140,93,0.20);
  }
  html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    font-family: 'Nunito', sans-serif; color: var(--fg);
  }
  [data-testid="stSidebar"] { background:#FEFCF7 !important; border-right:1.5px solid var(--border); }
  [data-testid="stSidebar"] * { color:var(--fg) !important; }
  [data-testid="stSidebar"] [data-baseweb="select"]>div {
    background:rgba(255,255,255,0.6)!important; border:1.5px solid var(--border)!important; border-radius:9999px!important; }
  [data-testid="stSidebar"] [role="listbox"] { background:var(--bg)!important; border-radius:1.5rem!important; }
  [data-testid="stSidebar"] [role="option"] { color:var(--fg)!important; }
  [data-testid="stSidebar"] [role="option"]:hover { background:var(--muted)!important; }
  [data-testid="stSidebar"] hr { border-color:var(--border)!important; opacity:0.6; }
  .hdr {
    background:linear-gradient(135deg,var(--primary) 0%,#4a5e40 55%,var(--secondary) 100%);
    padding:16px 24px; border-radius:2rem; margin-bottom:18px;
    display:flex; align-items:center; gap:14px;
    box-shadow:var(--shadow-clay); position:relative; overflow:hidden;
  }
  .hdr::after { content:''; position:absolute; width:240px; height:240px;
    background:rgba(255,255,255,0.06); border-radius:60% 40% 30% 70%/60% 30% 70% 40%;
    top:-80px; right:-60px; pointer-events:none; }
  .hdr-title { font-family:'Fraunces',serif; color:var(--primary-f); font-size:1.15rem; font-weight:700; }
  .hdr-sub { color:rgba(243,244,241,0.72); font-size:0.78rem; margin-top:2px; }
  .hdr-date { background:rgba(255,255,255,0.12); color:var(--primary-f);
    border-radius:9999px; padding:8px 16px; font-size:0.8rem; text-align:right;
    backdrop-filter:blur(4px); z-index:1; }
  .sec-title {
    font-family:'Fraunces',serif; font-size:0.95rem; font-weight:700;
    color:var(--primary); border-bottom:2px solid var(--accent);
    padding-bottom:5px; margin-bottom:14px;
  }
  .kpi { background:rgba(254,252,247,0.92); border:1.5px solid rgba(222,216,207,0.55);
    border-radius:1.5rem; padding:14px 16px; box-shadow:var(--shadow-moss);
    margin-bottom:8px; position:relative; overflow:hidden; transition:all 0.3s ease; }
  .kpi:hover { transform:translateY(-2px); box-shadow:var(--shadow-clay); }
  .kpi::after { content:''; position:absolute; width:70px; height:70px;
    background:rgba(93,112,82,0.05); border-radius:60% 40% 30% 70%/60% 30% 70% 40%;
    bottom:-18px; right:-16px; }
  .kpi-val { font-family:'Fraunces',serif; font-size:1.7rem; font-weight:700; color:var(--primary); }
  .kpi-red { color:var(--destructive)!important; }
  .kpi-grn { color:var(--primary)!important; }
  .kpi-lbl { font-size:0.73rem; color:var(--muted-f); margin-top:4px; }
  .top5-card {
    background:rgba(254,252,247,0.92); border:1.5px solid rgba(222,216,207,0.55);
    border-radius:1.5rem; padding:14px 18px; box-shadow:var(--shadow-moss);
    height:100%;
  }
  .top5-title { font-family:'Fraunces',serif; font-size:0.88rem; font-weight:700;
    color:var(--primary); margin-bottom:10px; border-bottom:1px solid var(--accent); padding-bottom:6px; }
  .top5-item { display:flex; justify-content:space-between; align-items:center;
    padding:6px 0; border-bottom:1px solid rgba(222,216,207,0.3); }
  .top5-item:last-child { border-bottom:none; }
  .top5-name { font-size:0.85rem; font-weight:600; color:var(--fg); }
  .top5-val-red { font-family:'Fraunces',serif; font-size:1rem; font-weight:700;
    color:var(--destructive); }
  .top5-val-grn { font-family:'Fraunces',serif; font-size:1rem; font-weight:700;
    color:var(--primary); }
  div[data-testid="stTabs"] button { font-family:'Nunito',sans-serif!important;
    color:var(--muted-f)!important; border-radius:9999px!important; padding:6px 14px!important; }
  div[data-testid="stTabs"] button[aria-selected="true"] {
    color:var(--primary)!important; background:var(--muted)!important; font-weight:700!important; }
  div[data-testid="stButton"]>button {
    background:var(--primary)!important; color:var(--primary-f)!important;
    border:none!important; border-radius:9999px!important;
    font-family:'Nunito',sans-serif!important; font-weight:700!important;
    box-shadow:var(--shadow-moss)!important; transition:all 0.3s ease!important; }
  div[data-testid="stButton"]>button:hover { transform:scale(1.03)!important; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def iniciar_gee():
    try:
        init_gee(dict(st.secrets) if "GEE_SERVICE_ACCOUNT" in st.secrets else None)
    except:
        init_gee()

iniciar_gee()

@st.cache_data(ttl=86400)
def obter_data():
    return get_latest_date()

@st.cache_data(ttl=86400)
def obter_tocantins():
    return get_tocantins_names(ASSETS["tocantins"])

@st.cache_data(ttl=86400)
def obter_display_map():
    return get_tocantins_display_names(ASSETS["tocantins"])

current_year, current_month, current_day = obter_data()
MESES = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]

tocantins_names   = obter_tocantins()
tocantins_disp    = obter_display_map()
toc_display_names = sorted([n.replace("\xa0"," ").strip() for n in tocantins_names if n])
GRUPOS["Tocantins-Araguaia"] = toc_display_names

# ── HEADER ────────────────────────────────────────────────────
logo_html = f'<img src="{LOGO_WWF}" style="height:48px;margin-right:14px">' if LOGO_WWF else ""
# Header sera renderizado APOS carregar os dados do lago
_header_placeholder = st.empty()

# ── SIDEBAR ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Filtros")
    grupo_sel = st.selectbox("Grupo", list(GRUPOS.keys()))
    lagos_grupo = GRUPOS[grupo_sel]
    is_toc = grupo_sel == "Tocantins-Araguaia"
    nf     = "Name" if is_toc else "name"
    asset  = ASSETS["tocantins"] if is_toc else ASSETS["lagos"]

    lago_disp = st.selectbox("Lago / Area",
        lagos_grupo if lagos_grupo else ["Carregando..."])
    lago_sel = tocantins_disp.get(lago_disp, lago_disp) if is_toc else lago_disp

    mes_sel = st.selectbox("Mes de analise", MESES, index=current_month-1)
    mes_num = MESES.index(mes_sel) + 1

    anos_disp = list(range(2023, current_year + 1))
    ano_sel   = st.selectbox("Ano de analise", list(reversed(anos_disp)), index=0)

    st.divider()
    if st.button("Atualizar"):
        st.cache_data.clear()
        st.rerun()
    st.markdown("""
    <div style="font-size:0.73rem;color:var(--muted-f);line-height:1.7;margin-top:8px">
      © WWF Brasil · Pedro Galve & Juliano Schirmbeck
    </div>""", unsafe_allow_html=True)

# ── CARREGA DADOS DO LAGO SELECIONADO ─────────────────────────
@st.cache_data(ttl=3600)
def load_serie(lago, nf, asset, cy, cm):
    # Hibrido: MOD11A2 para historico, MOD11A1 para mes atual
    return get_monthly_temperature_hybrid(lago, asset, ANO_BASE, cy, cm, nf)

@st.cache_data(ttl=3600)
def load_stats(lago, nf, asset, sy, sm):
    return get_temp_stats(lago, asset, sy, sm, nf)

@st.cache_data(ttl=3600)
def load_focos(lago, sy, sm, dyn):
    geom_src = None
    if dyn:
        try:
            feat = get_feature(lago, ASSETS["tocantins"], "Name")
            geom_src = feat.geometry()
        except: pass
    f5  = get_focos_count_periodo(lago, ASSETS["buffers"], 5000,  sy, sm, dynamic=dyn, geom_src=geom_src)
    f10 = get_focos_count_periodo(lago, ASSETS["buffers"], 10000, sy, sm, dynamic=dyn, geom_src=geom_src)
    return f5, f10

@st.cache_data(ttl=3600)
def load_all_lakes(lagos, asset, ano_base, cy, cm, nf):
    return get_all_lakes_temp_acumulado(lagos, asset, ano_base, cy, cm, nf)

@st.cache_data(ttl=600)  # 10 min
def load_temp_dia(lago, nf, asset):
    """Temperatura do dia mais recente (MOD11A1) e data."""
    return get_temp_latest_day(lago, asset, nf)

@st.cache_data(ttl=600)  # 10 min — dados diarios mudam com frequencia
def load_diario(lago, nf, asset, cy, cm):
    # Temperatura diaria do mes atual (MOD11A1) — cache de 30min
    return get_daily_temperature_current_month(lago, asset, cy, cm, nf)

@st.cache_data(ttl=3600)
def load_focos_serie(lago, cy, cm, dyn):
    geom_src = None
    if dyn:
        try:
            feat = get_feature(lago, ASSETS["tocantins"], "Name")
            geom_src = feat.geometry()
        except: pass
    df5  = get_monthly_focos(lago, ASSETS["buffers"], 5000,  ANO_BASE, cy, cm, dynamic=dyn, geom_src=geom_src)
    df10 = get_monthly_focos(lago, ASSETS["buffers"], 10000, ANO_BASE, cy, cm, dynamic=dyn, geom_src=geom_src)
    return df5, df10

# Carrega dado mais recente do lago ANTES do header
with st.spinner("Carregando dados..."):
    df_serie       = load_serie(lago_sel, nf, asset, current_year, current_month)
    t_a, t_p, t_h  = load_stats(lago_sel, nf, asset, ano_sel, mes_num)
    f5, f10        = load_focos(lago_sel, ano_sel, mes_num, is_toc)
    df_f5, df_f10  = load_focos_serie(lago_sel, current_year, current_month, is_toc)
    df_diario     = load_diario(lago_sel, nf, asset, current_year, current_month)
    t_dia, data_dia = load_temp_dia(lago_sel, nf, asset)

# Renderiza header com data correta do lago selecionado
_data_header = data_dia if data_dia else f"{current_day:02d}/{MESES[current_month-1]}/{current_year}"
_label_header = "Ultimo dado valido (MOD11A1)" if data_dia else "Referencia MODIS"
_header_placeholder.markdown(f"""
<div class=\"hdr\">
  {logo_html}
  <div style=\"flex:1;z-index:1\">
    <div class=\"hdr-title\">Analises e Estatisticas — Lagos Amazonicos</div>
    <div class=\"hdr-sub\">Painel analitico completo — WWF Brasil</div>
  </div>
  <div class=\"hdr-date\" style=\"z-index:1\">
    {_label_header}<br><b>{_data_header}</b>
  </div>
</div>
""", unsafe_allow_html=True)

MESES_LABEL = MESES

# ── KPIs ──────────────────────────────────────────────────────
st.markdown(f'<div class="sec-title">Resumo — {lago_disp} · {mes_sel}/{ano_sel}</div>',
            unsafe_allow_html=True)

k1,k2,k3,k4,k5 = st.columns(5)
for col, val, lbl, cls in [
    (k1, f"{t_a:.1f} °C" if t_a else "s/d", f"Temperatura atual", "kpi-val"),
    (k2, (f"+{round(t_a-t_p,1)}" if t_a and t_p and t_a-t_p>0 else f"{round(t_a-t_p,1)}" if t_a and t_p else "s/d") + (" °C" if t_a and t_p else ""),
     f"Desvio vs {ANO_BASE}", "kpi-red" if t_a and t_p and t_a-t_p>1 else "kpi-grn"),
    (k3, (f"+{round(t_a-t_h,1)}" if t_a and t_h and t_a-t_h>0 else f"{round(t_a-t_h,1)}" if t_a and t_h else "s/d") + (" °C" if t_a and t_h else ""),
     "Desvio vs media historica", "kpi-red" if t_a and t_h and t_a-t_h>1 else "kpi-grn"),
    (k4, str(f5),  "Focos calor (5 km)",  "kpi-red" if f5 and f5>20 else "kpi-val"),
    (k5, str(f10), "Focos calor (10 km)", "kpi-red" if f10 and f10>20 else "kpi-val"),
]:
    with col:
        st.markdown(f'''<div class="kpi">
          <div class="kpi-val {cls}">{val}</div>
          <div class="kpi-lbl">{lbl}</div>
        </div>''', unsafe_allow_html=True)

st.markdown("")

# ── ABAS ──────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "Serie Temporal",
    "Comparativo entre Lagos",
    "Focos de Calor",
])

# ═══════════════════════════════════════════════════════════════
# ABA 1 — SERIE TEMPORAL + GRAFICOS DE DESVIO
# ═══════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="sec-title">Serie temporal de temperatura</div>',
                unsafe_allow_html=True)

    if not df_serie.empty:
        anos = sorted(df_serie["ano"].unique())
        CORES_LINHA = {anos[0]: "#DED8CF", anos[-1]: "#5D7052"}
        if len(anos) > 1: CORES_LINHA[anos[-2]] = "#C18C5D"

        # Usa grafico hibrido com marcador especial para mes atual
        fig_serie_h = grafico_temperatura_mensal_hibrido(df_serie, lago_disp, current_year, mes_num)
        if fig_serie_h:
            st.plotly_chart(fig_serie_h, use_container_width=True)

        # Grafico de avanco diario do mes atual
        st.markdown(
            f'<div class="sec-title">Avanco diario — {mes_sel}/{ano_sel} (dado mais recente)</div>',
            unsafe_allow_html=True)
        fig_day = grafico_temperatura_diaria(df_diario, lago_disp, mes_sel, ano_sel)
        if fig_day:
            st.plotly_chart(fig_day, use_container_width=True)
            st.caption(f"★ {len(df_diario)} dias com dado disponivel em {mes_sel}/{ano_sel} · Fonte: MOD11A1 (diario) · Atraso tipico: 2-5 dias")
        else:
            st.info("Dados diarios ainda nao disponiveis para este mes.")


        # ── Graficos de desvio por mes ─────────────────────────────────
        st.markdown(
            f'<div class="sec-title">Desvio mensal de temperatura — {lago_disp}</div>',
            unsafe_allow_html=True)

        # Calcula desvios mes a mes
        df_cur  = df_serie[df_serie["ano"]==anos[-1]].set_index("mes")
        df_base = df_serie[df_serie["ano"]==anos[0]].set_index("mes")
        df_mh   = df_serie[df_serie["ano"]<anos[-1]].groupby("mes")["temperatura"].mean()

        meses_comuns = sorted(set(df_cur.index) & set(df_base.index) & set(df_mh.index))
        dif_base_mes = [round(df_cur.loc[m,"temperatura"] - df_base.loc[m,"temperatura"], 2)
                        for m in meses_comuns
                        if pd.notna(df_cur.loc[m,"temperatura"]) and pd.notna(df_base.loc[m,"temperatura"])]
        dif_avg_mes  = [round(df_cur.loc[m,"temperatura"] - df_mh.loc[m], 2)
                        for m in meses_comuns
                        if pd.notna(df_cur.loc[m,"temperatura"]) and pd.notna(df_mh.loc[m])]
        meses_labels = [MESES_LABEL[m-1] for m in meses_comuns[:len(dif_base_mes)]]

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            fig_d1 = go.Figure(go.Bar(
                x=meses_labels, y=dif_base_mes,
                marker_color=["#A85448" if v>0 else "#5D7052" for v in dif_base_mes],
                text=[f"{v:+.1f}" for v in dif_base_mes],
                textposition="outside",
                hovertemplate="Mes: %{x}<br>Dif vs %{customdata}: %{y:.2f}°C<extra></extra>",
                customdata=[anos[0]]*len(meses_labels)
            ))
            fig_d1.add_hline(y=0, line_color="#2C2C24", line_width=1)
            fig_d1.update_layout(
                title=f"Desvio mensal vs {anos[0]} — {lago_disp}",
                xaxis=dict(title="Mes", tickfont=dict(color="#2C2C24")),
                yaxis=dict(title="Dif temperatura (°C)",
                           showgrid=True, gridcolor="#F0EBE5",
                           tickfont=dict(color="#2C2C24")),
                plot_bgcolor="#FDFCF8", paper_bgcolor="#FDFCF8",
                height=280, margin=dict(l=55,r=20,t=50,b=40),
                font=dict(family="Nunito, sans-serif")
            )
            st.plotly_chart(fig_d1, use_container_width=True)

        with col_d2:
            fig_d2 = go.Figure(go.Bar(
                x=meses_labels, y=dif_avg_mes,
                marker_color=["#A85448" if v>0 else "#5D7052" for v in dif_avg_mes],
                text=[f"{v:+.1f}" for v in dif_avg_mes],
                textposition="outside",
                hovertemplate="Mes: %{x}<br>Dif vs media: %{y:.2f}°C<extra></extra>"
            ))
            fig_d2.add_hline(y=0, line_color="#2C2C24", line_width=1)
            fig_d2.update_layout(
                title=f"Desvio mensal vs media historica — {lago_disp}",
                xaxis=dict(title="Mes", tickfont=dict(color="#2C2C24")),
                yaxis=dict(title="Dif temperatura (°C)",
                           showgrid=True, gridcolor="#F0EBE5",
                           tickfont=dict(color="#2C2C24")),
                plot_bgcolor="#FDFCF8", paper_bgcolor="#FDFCF8",
                height=280, margin=dict(l=55,r=20,t=50,b=40),
                font=dict(family="Nunito, sans-serif")
            )
            st.plotly_chart(fig_d2, use_container_width=True)

# ═══════════════════════════════════════════════════════════════
# ABA 2 — COMPARATIVO ENTRE LAGOS
# ═══════════════════════════════════════════════════════════════
with tab2:
    # Botao para calcular
    col_btn, col_info = st.columns([2, 3])
    with col_btn:
        run_todos = st.button(
            f"Calcular comparativo — Jan a {mes_sel}/{ano_sel}")
    with col_info:
        st.caption(
            f"Calcula diferencas de temperatura acumuladas de Janeiro a {mes_sel}/{ano_sel} "
            "para todos os lagos. Resultado salvo na sessao.")

    if run_todos:
        prog = st.progress(0, text="Iniciando calculo batch no GEE...")
        with st.spinner(f"Calculando {len(GRUPOS[grupo_sel])} lagos..."):
            prog.progress(30, text="Calculando temperaturas em batch...")
            df_todos_calc = load_all_lakes(
                GRUPOS[grupo_sel], asset, ANO_BASE, ano_sel, mes_num, nf)
            prog.progress(100, text="Concluido!")
        st.session_state["df_todos"] = df_todos_calc
        prog.empty()

    df_todos = st.session_state.get("df_todos", None)

    if df_todos is not None and not df_todos.empty:
        df_v = df_todos.dropna(subset=["dif_base","dif_avg"]).copy()

        # ── Estimativas do mes ─────────────────────────────────────
        df_v["dif_mes_est_base"] = (df_v["dif_base"] / mes_num).round(2)
        df_v["dif_mes_est_avg"]  = (df_v["dif_avg"]  / mes_num).round(2)

        # ── Top 5 em 4 colunas ─────────────────────────────────────
        st.markdown(
            f'<div class="sec-title">Top 5 lagos com maior desvio — {mes_sel}/{ano_sel}</div>',
            unsafe_allow_html=True)

        def render_top5(df_col, col_name, titulo, unidade="°C"):
            df_sorted = df_col.dropna(subset=[col_name]).sort_values(
                col_name, ascending=False).head(5)
            items = ""
            for _, row in df_sorted.iterrows():
                val = row[col_name]
                cls = "top5-val-red" if val > 0 else "top5-val-grn"
                sinal = "+" if val > 0 else ""
                items += f"""<div class="top5-item">
                  <span class="top5-name">{row["Lago"]}</span>
                  <span class="{cls}">{sinal}{val:.1f}{unidade}</span>
                </div>"""
            return f'''<div class="top5-card">
              <div class="top5-title">{titulo}</div>
              {items}
            </div>'''

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(render_top5(df_v, "dif_mes_est_base",
                f"Desvio do mes vs {ANO_BASE}"), unsafe_allow_html=True)
        with c2:
            st.markdown(render_top5(df_v, "dif_mes_est_avg",
                "Desvio do mes vs media"), unsafe_allow_html=True)
        with c3:
            st.markdown(render_top5(df_v, "dif_base",
                f"Soma acumulada vs {ANO_BASE}"), unsafe_allow_html=True)
        with c4:
            st.markdown(render_top5(df_v, "dif_avg",
                "Soma acumulada vs media"), unsafe_allow_html=True)

        st.markdown("")

        # ── Tabela completa de todos os lagos ──────────────────────
        st.markdown(
            f'<div class="sec-title">Todos os lagos — {mes_sel}/{ano_sel}</div>',
            unsafe_allow_html=True)

        df_tabela = df_v[["Lago","dif_mes_est_base","dif_mes_est_avg",
                           "dif_base","dif_avg"]].copy()
        df_tabela.columns = [
            "Lago",
            f"Desvio mes vs {ANO_BASE} (°C)",
            "Desvio mes vs media (°C)",
            f"Soma acum vs {ANO_BASE} (°C)",
            "Soma acum vs media (°C)"
        ]
        df_tabela = df_tabela.sort_values(
            f"Soma acum vs {ANO_BASE} (°C)", ascending=False)

        from utils.charts import colorir_dif
        cols_dif = [f"Desvio mes vs {ANO_BASE} (°C)",
                    "Desvio mes vs media (°C)",
                    f"Soma acum vs {ANO_BASE} (°C)",
                    "Soma acum vs media (°C)"]
        styled_tab = (df_tabela.style
            .map(colorir_dif, subset=cols_dif)
            .highlight_null(color="#f5f5f5")
            .format("{:+.2f}", subset=cols_dif, na_rep="s/d"))
        st.dataframe(styled_tab, use_container_width=True, hide_index=True)
        st.markdown("")

        # ── 4 graficos de ranking ──────────────────────────────────────
        st.markdown(
            f'<div class="sec-title">Ranking de temperatura — todos os lagos (Jan a {mes_sel}/{ano_sel})</div>',
            unsafe_allow_html=True)

        def fig_ranking(df_in, col, titulo, cor):
            df_s = df_in.sort_values(col, ascending=False)
            fig = go.Figure(go.Bar(
                x=df_s["Lago"], y=df_s[col],
                marker_color=[cor if v >= 0 else "#5D7052" for v in df_s[col]],
                text=df_s[col].round(1),
                textposition="outside",
                hovertemplate="%{x}<br>%{y:.1f} °C<extra></extra>"
            ))
            fig.add_hline(y=0, line_color="#2C2C24", line_width=1)
            fig.update_layout(
                title=titulo,
                xaxis=dict(tickangle=-45, tickfont=dict(size=9, color="#2C2C24"),
                           title="Lago"),
                yaxis=dict(showgrid=True, gridcolor="#F0EBE5",
                           tickfont=dict(color="#2C2C24")),
                plot_bgcolor="#FDFCF8", paper_bgcolor="#FDFCF8",
                height=360, margin=dict(l=50,r=20,t=55,b=130),
                font=dict(family="Nunito, sans-serif")
            )
            return fig

        st.plotly_chart(fig_ranking(
            df_v, "dif_mes_est_base",
            f"Desvio do mes vs {ANO_BASE} — {mes_sel}/{ano_sel}",
            "#A85448"), use_container_width=True)

        st.plotly_chart(fig_ranking(
            df_v, "dif_mes_est_avg",
            f"Desvio do mes vs media historica — {mes_sel}/{ano_sel}",
            "#A85448"), use_container_width=True)

        st.plotly_chart(fig_ranking(
            df_v, "dif_base",
            f"Soma acumulada vs {ANO_BASE} — Jan a {mes_sel}/{ano_sel}",
            "#A85448"), use_container_width=True)

        st.plotly_chart(fig_ranking(
            df_v, "dif_avg",
            f"Soma acumulada vs media historica — Jan a {mes_sel}/{ano_sel}",
            "#A85448"), use_container_width=True)

        # ── Mapas de distribuicao espacial ────────────────────────────
        st.markdown(
            '<div class="sec-title">Distribuicao espacial — diferenca de temperatura</div>',
            unsafe_allow_html=True)

        df_mapa  = df_todos.dropna(subset=["centroid","dif_base"]).copy()
        df_mapa["lon"] = df_mapa["centroid"].apply(lambda c: c[0])
        df_mapa["lat"] = df_mapa["centroid"].apply(lambda c: c[1])

        df_mapa2 = df_todos.dropna(subset=["centroid","dif_avg"]).copy()
        df_mapa2["lon"] = df_mapa2["centroid"].apply(lambda c: c[0])
        df_mapa2["lat"] = df_mapa2["centroid"].apply(lambda c: c[1])

        def cor_dif(val, vmin, vmax):
            if val is None: return "#888888"
            norm = (val - vmin) / (vmax - vmin) if vmax != vmin else 0.5
            norm = max(0, min(1, norm))
            if norm < 0.5:
                r = int(255 * norm * 2); g = 160; b = 0
            else:
                r = 200; g = int(160 * (1-(norm-0.5)*2)); b = 0
            return f"#{r:02x}{g:02x}{b:02x}"

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.caption(f"Diferenca acumulada vs {ANO_BASE} — verde=menor, laranja/vermelho=maior")
            m1 = folium.Map(location=[-4.5,-61], zoom_start=5, tiles="CartoDB positron")
            vals1 = df_mapa["dif_base"].dropna()
            vmin1, vmax1 = vals1.min(), vals1.max()
            for _, row in df_mapa.iterrows():
                cor = cor_dif(row["dif_base"], vmin1, vmax1)
                folium.CircleMarker(
                    location=[row["lat"], row["lon"]],
                    radius=11, color=cor, fill=True,
                    fill_color=cor, fill_opacity=0.88,
                    popup=folium.Popup(
                        f"<b>{row['Lago']}</b><br>Dif acum vs {ANO_BASE}: <b>{row['dif_base']:.1f}°C</b>",
                        max_width=200),
                    tooltip=f"{row['Lago']}: {row['dif_base']:+.1f}°C"
                ).add_to(m1)
            st_folium(m1, height=400, use_container_width=True)

        with col_m2:
            st.caption("Diferenca acumulada vs media historica — verde=menor, laranja/vermelho=maior")
            m2 = folium.Map(location=[-4.5,-61], zoom_start=5, tiles="CartoDB positron")
            vals2 = df_mapa2["dif_avg"].dropna()
            vmin2, vmax2 = vals2.min(), vals2.max()
            for _, row in df_mapa2.iterrows():
                cor = cor_dif(row["dif_avg"], vmin2, vmax2)
                folium.CircleMarker(
                    location=[row["lat"], row["lon"]],
                    radius=11, color=cor, fill=True,
                    fill_color=cor, fill_opacity=0.88,
                    popup=folium.Popup(
                        f"<b>{row['Lago']}</b><br>Dif acum vs media: <b>{row['dif_avg']:.1f}°C</b>",
                        max_width=200),
                    tooltip=f"{row['Lago']}: {row['dif_avg']:+.1f}°C"
                ).add_to(m2)
            st_folium(m2, height=400, use_container_width=True)

        # Download
        csv_t = df_todos.drop(columns=["centroid"], errors="ignore")                        .to_csv(index=False).encode("utf-8")
        st.download_button(
            f"Baixar comparativo CSV — {mes_sel}/{ano_sel}",
            csv_t, f"comparativo_lagos_{ano_sel}_{mes_num:02d}.csv",
            mime="text/csv")
    else:
        st.info("Clique no botao acima para calcular o comparativo entre todos os lagos.")

# ═══════════════════════════════════════════════════════════════
# ABA 3 — FOCOS DE CALOR
# ═══════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="sec-title">Focos de calor — serie mensal</div>',
                unsafe_allow_html=True)

    CORES_ANOS_F = {0: "#DED8CF", 1: "#C18C5D", 2: "#5D7052"}
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        st.markdown(f'''<div class="kpi">
          <div class="kpi-val {"kpi-red" if f5 and f5>20 else "kpi-val"}">{f5}</div>
          <div class="kpi-lbl">Focos no mes selecionado (5 km)</div>
        </div>''', unsafe_allow_html=True)
    with col_f2:
        st.markdown(f'''<div class="kpi">
          <div class="kpi-val {"kpi-red" if f10 and f10>20 else "kpi-val"}">{f10}</div>
          <div class="kpi-lbl">Focos no mes selecionado (10 km)</div>
        </div>''', unsafe_allow_html=True)

    st.markdown("")

    def fig_focos(df_f, dist_km):
        if df_f is None or df_f.empty: return None
        anos_f = sorted(df_f["ano"].unique())
        fig = go.Figure()
        for i, ano in enumerate(anos_f):
            sub = df_f[df_f["ano"]==ano].dropna(subset=["focos"])
            cor = CORES_ANOS_F.get(i, "#90a4ae")
            fig.add_trace(go.Bar(
                x=sub["mes"], y=sub["focos"],
                name=str(ano), marker_color=cor,
                hovertemplate=f"<b>{ano}</b><br>Mes: %{{x}}<br>Focos: %{{y}}<extra></extra>"
            ))
        fig.update_layout(
            title=f"Focos de calor mensais — buffer {dist_km} km",
            xaxis=dict(tickmode="array", tickvals=list(range(1,13)),
                       ticktext=MESES_LABEL, title="Mes",
                       tickfont=dict(color="#2C2C24")),
            yaxis=dict(title="Numero de focos", showgrid=True,
                       gridcolor="#F0EBE5", tickfont=dict(color="#2C2C24")),
            barmode="group",
            plot_bgcolor="#FDFCF8", paper_bgcolor="#FDFCF8",
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                        font=dict(color="#2C2C24")),
            height=290, margin=dict(l=55,r=20,t=50,b=55),
            font=dict(family="Nunito, sans-serif")
        )
        return fig

    col_fc1, col_fc2 = st.columns(2)
    with col_fc1:
        fig_f5 = fig_focos(df_f5, 5)
        if fig_f5: st.plotly_chart(fig_f5, use_container_width=True)
        else: st.info("Sem dados de focos (5 km).")
    with col_fc2:
        fig_f10 = fig_focos(df_f10, 10)
        if fig_f10: st.plotly_chart(fig_f10, use_container_width=True)
        else: st.info("Sem dados de focos (10 km).")

    # Acumulado
    if df_f5 is not None and not df_f5.empty:
        ano_cur = sorted(df_f5["ano"].unique())[-1]
        fig_ac = go.Figure()
        for df_f, dist, cor in [(df_f5,"5km","#C18C5D"),(df_f10,"10km","#A85448")]:
            sub = df_f[df_f["ano"]==ano_cur].dropna(subset=["focos"]).copy()
            sub["acum"] = sub["focos"].cumsum()
            fig_ac.add_trace(go.Scatter(
                x=sub["mes"], y=sub["acum"],
                mode="lines+markers", name=f"Buffer {dist}",
                line=dict(color=cor, width=2.5),
                hovertemplate=f"Buffer {dist}<br>Mes: %{{x}}<br>Acum: %{{y}}<extra></extra>"
            ))
        fig_ac.update_layout(
            title=f"Focos acumulados em {ano_cur} — comparativo de buffers",
            xaxis=dict(tickmode="array", tickvals=list(range(1,13)),
                       ticktext=MESES_LABEL, title="Mes",
                       tickfont=dict(color="#2C2C24")),
            yaxis=dict(title="Focos acumulados", showgrid=True,
                       gridcolor="#F0EBE5", tickfont=dict(color="#2C2C24")),
            plot_bgcolor="#FDFCF8", paper_bgcolor="#FDFCF8",
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                        font=dict(color="#2C2C24")),
            height=280, margin=dict(l=55,r=20,t=50,b=55),
            font=dict(family="Nunito, sans-serif")
        )
        st.plotly_chart(fig_ac, use_container_width=True)

# ── RODAPE ────────────────────────────────────────────────────
st.divider()
st.markdown(f"""
<div style="text-align:center;color:var(--muted-f);font-size:0.76rem;padding:6px">
  Dados: Google Earth Engine · MODIS Terra · VIIRS/SNPP<br>
  WWF Brasil · Pedro Galve & Juliano Schirmbeck · {current_year}
</div>""", unsafe_allow_html=True)

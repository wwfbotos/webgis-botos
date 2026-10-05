import plotly.graph_objects as go
import pandas as pd

MESES = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]

def cor_por_ano(ano, ref_year):
    if ano == ref_year:       return "#1565c0"
    elif ano == ref_year - 1: return "#e65100"
    else:                     return "#78909c"

def _layout(titulo, subtitulo, ylab, height=300):
    return dict(
        title=dict(text=f"<b>{titulo}</b>",
                   font=dict(size=13, color="#1a237e"), x=0),
        annotations=[dict(text=subtitulo, xref="paper", yref="paper",
                          x=0, y=1.01, xanchor="left", yanchor="bottom",
                          font=dict(size=10, color="#546e7a"), showarrow=False)],
        xaxis=dict(title="<b>Mes</b>", tickmode="array",
                   tickvals=list(range(1,13)), ticktext=MESES,
                   tickfont=dict(size=10, color="#37474f"),
                   showgrid=True, gridcolor="#eceff1", linecolor="#90a4ae"),
        yaxis=dict(title=f"<b>{ylab}</b>",
                   tickfont=dict(size=10, color="#37474f"),
                   showgrid=True, gridcolor="#eceff1", linecolor="#90a4ae"),
        plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(title=dict(text="<b>Ano</b>",
                               font=dict(size=10, color="#37474f")),
                    orientation="h", yanchor="top", y=-0.22,
                    xanchor="left", x=0,
                    font=dict(size=10, color="#37474f"),
                    bgcolor="white", bordercolor="#eceff1", borderwidth=1),
        margin=dict(l=60, r=20, t=55, b=80),
        height=height,
        hoverlabel=dict(bgcolor="white", font_size=11, font_color="#1a1a1a")
    )

def grafico_temperatura(df, lago, ref_year, sel_month):
    anos = sorted(df["ano"].unique())
    fig = go.Figure()
    for ano in anos:
        sub = df[df["ano"]==ano].dropna(subset=["temperatura"])
        cor = cor_por_ano(ano, ref_year)
        fig.add_trace(go.Scatter(
            x=sub["mes"], y=sub["temperatura"],
            mode="lines+markers", name=str(ano),
            line=dict(color=cor,
                      width=3 if ano==ref_year else 1.5,
                      dash="solid" if ano>=ref_year-1 else "dot"),
            marker=dict(size=6 if ano==ref_year else 4),
            hovertemplate=f"<b>{ano}</b><br>Mes: %{{x}}<br>Temp: %{{y:.2f}} C<extra></extra>"
        ))
    fig.add_vline(x=sel_month, line_dash="dot",
                  line_color="#fb8c00", line_width=1.5,
                  annotation_text=MESES[sel_month-1],
                  annotation_font_color="#fb8c00",
                  annotation_font_size=10)
    fig.update_layout(**_layout(
        f"Temperatura Superficial — {lago}",
        "Fonte: MODIS Terra (MOD11A2) · Media mensal · graus C",
        "Temperatura (C)", height=290))
    return fig

def grafico_anomalia(df, lago, ref_year):
    df_hist = df[df["ano"]<ref_year].groupby("mes")["temperatura"].mean().reset_index()
    df_cur  = df[df["ano"]==ref_year].dropna(subset=["temperatura"])
    merged  = df_cur.merge(df_hist, on="mes", suffixes=("_cur","_hist"))
    if merged.empty: return None
    merged["anomalia"] = merged["temperatura_cur"] - merged["temperatura_hist"]
    colors = ["#e53935" if v>0 else "#1565c0" for v in merged["anomalia"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=merged["mes"], y=merged["anomalia"],
                         marker_color=colors, name="Anomalia",
                         hovertemplate="Mes: %{x}<br>Anomalia: %{y:.2f} C<extra></extra>"))
    fig.add_hline(y=0, line_color="#546e7a", line_width=1)
    fig.update_layout(**_layout(
        f"Anomalia Termica {ref_year} — {lago}",
        f"Diferenca entre {ref_year} e media historica · graus C",
        "Anomalia (C)", height=260))
    return fig

def grafico_boxplot(df, lago):
    fig = go.Figure()
    for mes in range(1,13):
        sub = df[df["mes"]==mes]["temperatura"].dropna()
        fig.add_trace(go.Box(y=sub, name=MESES[mes-1],
                             marker_color="#1565c0", showlegend=False,
                             boxmean=True,
                             hovertemplate=f"<b>{MESES[mes-1]}</b><br>%{{y:.2f}} C<extra></extra>"))
    lay = _layout(f"Distribuicao Historica — {lago}",
                  "Todos os anos disponíveis · MODIS Terra", "Temperatura (C)", 260)
    lay.pop("xaxis", None)
    fig.update_layout(**lay)
    fig.update_xaxes(tickfont=dict(size=10, color="#37474f"))
    return fig

def grafico_focos(df, lago, dist_km, ref_year):
    anos = sorted(df["ano"].unique())
    fig = go.Figure()
    for ano in anos:
        sub = df[df["ano"]==ano].dropna(subset=["focos"])
        cor = cor_por_ano(ano, ref_year)
        fig.add_trace(go.Bar(x=sub["mes"], y=sub["focos"],
                             name=str(ano), marker_color=cor,
                             hovertemplate=f"<b>{ano}</b><br>Mes: %{{x}}<br>Focos: %{{y}}<extra></extra>"))
    lay = _layout(f"Focos de Calor Mensais — {lago}",
                  f"Buffer {dist_km} km · Fonte: VIIRS/SNPP",
                  "Numero de focos", 270)
    lay["barmode"] = "group"
    fig.update_layout(**lay)
    return fig

def grafico_acumulado(df5, df10, lago, ref_year):
    fig = go.Figure()
    for df, dist, cor in [(df5,"5km","#e65100"),(df10,"10km","#b71c1c")]:
        sub = df[df["ano"]==ref_year].dropna(subset=["focos"]).copy()
        sub["acum"] = sub["focos"].cumsum()
        fig.add_trace(go.Scatter(x=sub["mes"], y=sub["acum"],
                                 mode="lines+markers", name=f"Buffer {dist}",
                                 line=dict(color=cor, width=2),
                                 hovertemplate=f"Buffer {dist}<br>Mes: %{{x}}<br>Acum: %{{y}}<extra></extra>"))
    fig.update_layout(**_layout(f"Focos Acumulados {ref_year} — {lago}",
                                "Comparativo buffer 5km vs 10km",
                                "Focos acumulados", 260))
    return fig

def colorir_temp(val):
    if pd.isna(val): return "background-color:#f5f5f5;color:#9e9e9e"
    norm = max(0, min(1, (val-24)/(31-24)))
    r = int(220+35*norm); g = int(220*(1-norm)); b = int(220*(1-norm))
    txt = "#000" if norm<0.6 else "#fff"
    return f"background-color:rgb({r},{g},{b});color:{txt};font-weight:600"

def colorir_dif(val):
    if pd.isna(val): return "background-color:#f5f5f5;color:#9e9e9e"
    norm = max(-1, min(1, val/5))
    if norm<=0:
        i=1+norm; r=int(220*i); g=int(220*i); b=220; txt="#000"
    else:
        r=220; g=int(220*(1-0.4*norm)); b=int(220*(1-norm))
        txt="#000" if norm<0.7 else "#fff"
    return f"background-color:rgb({r},{g},{b});color:{txt};font-weight:600"

def colorir_focos(val):
    if pd.isna(val): return "background-color:#f5f5f5;color:#9e9e9e"
    norm = min(1, val/50)
    r=int(200+55*norm); g=int(200*(1-norm)); b=int(200*(1-norm))
    txt="#000" if norm<0.6 else "#fff"
    return f"background-color:rgb({r},{g},{b});color:{txt};font-weight:600"

def grafico_temperatura_diaria(df_diario, lago_nome, mes_nome, ano):
    """
    Grafico de temperatura diaria do mes atual (MOD11A1).
    Mostra cada dia disponivel com marcador e linha de tendencia.
    """
    if df_diario is None or df_diario.empty:
        return None

    fig = go.Figure()

    # Linha principal
    fig.add_trace(go.Scatter(
        x=df_diario["dia"], y=df_diario["temperatura"],
        mode="lines+markers", name="Temp diaria",
        line=dict(color="#5D7052", width=2.5),
        marker=dict(size=7, color="#5D7052",
                    line=dict(color="white", width=1.5)),
        hovertemplate="Dia %{x}<br>%{y:.2f}°C<extra></extra>"
    ))

    # Media do mes
    media = df_diario["temperatura"].mean()
    fig.add_hline(y=media, line_dash="dash", line_color="#C18C5D",
                  line_width=1.5,
                  annotation_text=f"Media: {media:.1f}°C",
                  annotation_font_color="#C18C5D",
                  annotation_position="bottom right")

    # Linha de tendencia
    if len(df_diario) >= 3:
        import numpy as np
        z = np.polyfit(df_diario["dia"], df_diario["temperatura"], 1)
        p = np.poly1d(z)
        x_trend = list(range(df_diario["dia"].min(),
                             df_diario["dia"].max() + 1))
        fig.add_trace(go.Scatter(
            x=x_trend, y=[p(x) for x in x_trend],
            mode="lines", name="Tendencia",
            line=dict(color="#A85448", width=1.5, dash="dot"),
            hovertemplate="Tendencia: %{y:.2f}°C<extra></extra>"
        ))

    fig.update_layout(
        title=f"Temperatura diaria — {lago_nome} — {mes_nome}/{ano}",
        annotations=[dict(
            text="Fonte: MODIS Terra MOD11A1 (diario) · dado preliminar do mes",
            xref="paper", yref="paper",
            x=0, y=1.01, xanchor="left", yanchor="bottom",
            font=dict(size=9, color="#78786C"), showarrow=False
        )],
        xaxis=dict(title="Dia do mes",
                   tickfont=dict(color="#2C2C24"),
                   showgrid=True, gridcolor="#F0EBE5"),
        yaxis=dict(title="Temperatura (°C)",
                   tickfont=dict(color="#2C2C24"),
                   showgrid=True, gridcolor="#F0EBE5"),
        plot_bgcolor="#FDFCF8", paper_bgcolor="#FDFCF8",
        legend=dict(orientation="h", yanchor="bottom", y=1.06,
                    font=dict(color="#2C2C24")),
        height=300, margin=dict(l=55, r=20, t=65, b=50),
        font=dict(family="Nunito, sans-serif")
    )
    return fig

def grafico_temperatura_mensal_hibrido(df, lago_nome, ref_year, sel_month):
    """
    Serie temporal hibrida:
    - Linhas historicas: MOD11A2 (8 dias)
    - Ponto do mes atual: MOD11A1 (diario) — destacado com marcador diferente
    """
    anos = sorted(df["ano"].unique())
    CORES = {anos[0]: "#DED8CF"}
    if len(anos) > 1: CORES[anos[-2]] = "#C18C5D"
    CORES[anos[-1]] = "#5D7052"

    fig = go.Figure()
    for ano in anos:
        sub = df[df["ano"]==ano].dropna(subset=["temperatura"]).sort_values("mes")
        cor = CORES.get(ano, "#90a4ae")
        width = 3 if ano == anos[-1] else 1.5
        dash = "solid" if ano >= anos[-1]-1 else "dot"

        tem_atual = "produto" in sub.columns and (sub["produto"] == "MOD11A1").any()
        sub_normal = sub[sub["produto"] != "MOD11A1"] if "produto" in sub.columns else sub
        sub_atual  = sub[sub["produto"] == "MOD11A1"] if "produto" in sub.columns else pd.DataFrame()

        if tem_atual and not sub_atual.empty and not sub_normal.empty:
            # Linha historica
            fig.add_trace(go.Scatter(
                x=sub_normal["mes"], y=sub_normal["temperatura"],
                mode="lines+markers", name=str(ano),
                line=dict(color=cor, width=width, dash=dash),
                marker=dict(size=6),
                legendgroup=str(ano),
                hovertemplate=f"<b>{ano}</b><br>Mes: %{{x}}<br>%{{y:.2f}}°C (MOD11A2)<extra></extra>"
            ))
            # Linha pontilhada conectando ao ponto atual
            ultimo = sub_normal.iloc[-1]
            atual  = sub_atual.iloc[0]
            fig.add_trace(go.Scatter(
                x=[ultimo["mes"], atual["mes"]],
                y=[ultimo["temperatura"], atual["temperatura"]],
                mode="lines", showlegend=False,
                line=dict(color=cor, width=width, dash="dot"),
                hoverinfo="skip"
            ))
            # Estrela no ponto atual
            fig.add_trace(go.Scatter(
                x=sub_atual["mes"], y=sub_atual["temperatura"],
                mode="markers", name=f"{ano} (atual*)",
                marker=dict(symbol="star", size=16,
                            color=cor, line=dict(color="white", width=1.5)),
                legendgroup=str(ano),
                hovertemplate=f"<b>{ano} — preliminar (MOD11A1)</b><br>Mes: %{{x}}<br>%{{y:.2f}}°C<extra></extra>"
            ))
        else:
            fig.add_trace(go.Scatter(
                x=sub["mes"], y=sub["temperatura"],
                mode="lines+markers", name=str(ano),
                line=dict(color=cor, width=width, dash=dash),
                marker=dict(size=5 if ano != anos[-1] else 6),
                legendgroup=str(ano),
                hovertemplate=f"<b>{ano}</b><br>Mes: %{{x}}<br>%{{y:.2f}}°C<extra></extra>"
            ))

    # Media historica
    df_hist = df[df["ano"] < anos[-1]]
    if not df_hist.empty:
        mh = df_hist.groupby("mes")["temperatura"].mean()
        fig.add_trace(go.Scatter(
            x=mh.index, y=mh.values, mode="lines",
            name="Media historica",
            line=dict(color="#E6DCCD", width=1.5, dash="dash"),
            hovertemplate="Media historica<br>Mes: %{x}<br>%{y:.2f}°C<extra></extra>"
        ))

    fig.add_vline(x=sel_month, line_dash="dot",
                  line_color="#C18C5D", line_width=1.5,
                  annotation_text=MESES[sel_month-1],
                  annotation_font_color="#C18C5D")

    fig.update_layout(
        title=f"Temperatura superficial — {lago_nome}",
        annotations=[dict(
            text="MOD11A2 (8 dias) para historico · MOD11A1 (diario) para mes atual (*)",
            xref="paper", yref="paper",
            x=0, y=1.01, xanchor="left", yanchor="bottom",
            font=dict(size=9, color="#78786C"), showarrow=False
        )],
        xaxis=dict(title="Mes", tickmode="array",
                   tickvals=list(range(1,13)), ticktext=MESES,
                   tickfont=dict(color="#2C2C24"),
                   showgrid=True, gridcolor="#F0EBE5"),
        yaxis=dict(title="Temperatura (°C)",
                   tickfont=dict(color="#2C2C24"),
                   showgrid=True, gridcolor="#F0EBE5"),
        plot_bgcolor="#FDFCF8", paper_bgcolor="#FDFCF8",
        legend=dict(orientation="h", yanchor="bottom", y=1.1,
                    font=dict(color="#2C2C24")),
        height=320, margin=dict(l=55, r=20, t=75, b=55),
        font=dict(family="Nunito, sans-serif")
    )
    return fig

import ee
import pandas as pd
import streamlit as st
import time as time_module
from datetime import datetime

def init_gee(secrets=None):
    try:
        if secrets and "GEE_SERVICE_ACCOUNT" in secrets:
            creds = ee.ServiceAccountCredentials(
                secrets["GEE_SERVICE_ACCOUNT"],
                key_data=secrets["GEE_PRIVATE_KEY"]
            )
            ee.Initialize(creds)
        else:
            ee.Initialize(project="pedrogalve")
    except Exception as e:
        st.error(f"Erro GEE: {e}")
        st.stop()

def get_latest_date():
    """
    Retorna (year, month, day) do ultimo periodo do MOD11A2 (base historica).
    O MOD11A2 define o mes de referencia global do dashboard.
    A data do dado diario por lago e calculada em get_temp_latest_day.
    """
    col = ee.ImageCollection("MODIS/061/MOD11A2").sort("system:time_start", False)
    latest = col.first()
    date = ee.Date(latest.get("system:time_start"))
    info = date.getInfo()
    dt = datetime.utcfromtimestamp(info["value"] / 1000)
    return dt.year, dt.month, dt.day

def modis_temperature(image):
    lst = image.select("LST_Day_1km").multiply(0.02).subtract(273.15).rename("surface_temperature")
    return image.addBands(lst)

def corrections_landsat(image):
    optical = image.select("SR_B.*").multiply(0.0000275).add(-0.2)
    thermal = image.select("ST_B.*").multiply(0.00341802).add(149.0)
    image = image.addBands(optical, None, True).addBands(thermal, None, True)
    qa = image.select("QA_PIXEL")
    cloud = qa.bitwiseAnd(1 << 3).Or(qa.bitwiseAnd(1 << 4))
    image = image.updateMask(cloud.Not())
    lst = image.select("ST_B10").subtract(273.15).rename("surface_temperature")
    return image.addBands(lst)

def get_tile_url(image, vis_params):
    map_id = image.getMapId(vis_params)
    return map_id["tile_fetcher"].url_format

def get_feature(name, asset_id, name_field="name"):
    """Busca feature por nome — tenta variantes com xa0 e espaco normal."""
    fc = ee.FeatureCollection(asset_id)
    # 1. Busca direta
    result = fc.filter(ee.Filter.eq(name_field, name))
    if result.size().getInfo() > 0:
        return result
    # 2. Troca espaco normal por xa0
    name_xa0 = name.replace(" ", "\xa0")
    result = fc.filter(ee.Filter.eq(name_field, name_xa0))
    if result.size().getInfo() > 0:
        return result
    # 3. Remove xa0
    name_clean = name.replace("\xa0", " ").strip()
    result = fc.filter(ee.Filter.eq(name_field, name_clean))
    if result.size().getInfo() > 0:
        return result
    # 4. Busca por similaridade
    all_names = fc.aggregate_array(name_field).getInfo()
    name_norm = name.replace("\xa0", " ").strip().lower()
    for n in all_names:
        if n and name_norm in str(n).replace("\xa0", " ").lower():
            return fc.filter(ee.Filter.eq(name_field, n))
    return result

def get_tocantins_names(asset_id):
    """
    Carrega nomes do asset Tocantins-Araguaia.
    Retorna lista de nomes para display (sem xa0)
    e um dict mapeando display -> nome real no asset.
    """
    try:
        fc = ee.FeatureCollection(asset_id)
        names = fc.aggregate_array("Name").getInfo()
        result = []
        for n in names:
            if n:
                result.append(str(n))
        return sorted(result)
    except Exception as e:
        return []

def get_tocantins_display_names(asset_id):
    """Retorna dict: nome_display -> nome_real (com xa0 se necessario)."""
    try:
        fc = ee.FeatureCollection(asset_id)
        names = fc.aggregate_array("Name").getInfo()
        mapping = {}
        for n in names:
            if n:
                display = str(n).replace("\xa0", " ").strip()
                mapping[display] = str(n)
        return mapping
    except:
        return {}

def _safe_geometry(feat_collection):
    """
    Extrai geometria valida de uma FeatureCollection.
    Trata GeometryCollection extraindo o Polygon interno.
    """
    try:
        info = feat_collection.first().getInfo()
        raw  = info.get("geometry", {})
        gtype = raw.get("type", "")

        if gtype == "GeometryCollection":
            geoms = raw.get("geometries", [])
            # Prioridade: Polygon > MultiPolygon > LineString > qualquer outro
            for priority in ("Polygon", "MultiPolygon", "LineString",
                             "MultiLineString", "Point"):
                for g in geoms:
                    if g.get("type") == priority and g.get("coordinates"):
                        geom_ee = ee.Geometry(g)
                        return geom_ee, geom_ee.bounds()
            # Fallback: usa geometria do GEE
            geom = feat_collection.geometry()
            return geom, geom.bounds()

        elif gtype in ("Polygon","MultiPolygon","LineString",
                       "MultiLineString","Point"):
            geom_ee = ee.Geometry(raw)
            return geom_ee, geom_ee.bounds()

        else:
            geom = feat_collection.geometry()
            return geom, geom.bounds()

    except Exception as e:
        geom = feat_collection.geometry()
        return geom, geom.bounds()

def get_sentinel_tile(name, asset_id, start, end, name_field="name"):
    feat = get_feature(name, asset_id, name_field)
    _, bounds = _safe_geometry(feat)
    def mask_clouds(img):
        prob = img.select("MSK_CLDPRB").eq(0)
        scl = img.select("SCL")
        mask = prob.And(scl.neq(3)).And(scl.neq(10))
        return img.updateMask(mask)
    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterDate(start, end)
           .filterBounds(bounds)
           .map(mask_clouds)
           .median())
    vis = {"bands": ["B11", "B8", "B4"], "min": 155, "max": 4920, "gamma": 1}
    geom_safe, _ = _safe_geometry(feat)
    centroid = geom_safe.centroid().getInfo()["coordinates"]
    return get_tile_url(col, vis), centroid

def get_modis_tile(name, asset_id, start, end, name_field="name"):
    feat = get_feature(name, asset_id, name_field)
    _, bounds = _safe_geometry(feat)
    col = (ee.ImageCollection("MODIS/061/MOD11A2")
           .filterDate(start, end)
           .filterBounds(bounds)
           .map(modis_temperature)
           .select("surface_temperature")
           .median())
    vis = {"min": "15", "max": "35", "palette": "blue,green,yellow,orange,red"}
    return get_tile_url(col, vis)

def get_landsat_tile(name, asset_id, start, end, name_field="name"):
    feat = get_feature(name, asset_id, name_field)
    _, bounds = _safe_geometry(feat)
    col = (ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
           .merge(ee.ImageCollection("LANDSAT/LC08/C02/T1_L2"))
           .filterDate(start, end)
           .filterBounds(bounds)
           .map(corrections_landsat)
           .select("surface_temperature")
           .median())
    vis = {"min": "15", "max": "35", "palette": "blue,green,yellow,orange,red"}
    return get_tile_url(col, vis)

def get_focos_tiles(year, month):
    focos = ee.ImageCollection("NASA/LANCE/SNPP_VIIRS/C2")
    start1 = ee.Date.fromYMD(year, month, 1)
    mid    = start1.advance(15, "day")
    end1   = start1.advance(1, "month")
    img1 = focos.filterDate(start1, mid).select("confidence").max().gte(1).selfMask()
    img2 = focos.filterDate(mid, end1).select("confidence").max().gte(1).selfMask()
    url1 = get_tile_url(img1, {"palette": "ff0000"})
    url2 = get_tile_url(img2, {"palette": "ffaa00"})
    return url1, url2

def get_monthly_temperature(name, asset_id, ano_base, ref_year, ref_month, name_field="name"):
    """Busca temp mensal para anos: ano_base, ref_year-1, ref_year."""
    feat = get_feature(name, asset_id, name_field)
    geom = feat.geometry()
    anos = sorted(set([ano_base, ref_year - 1, ref_year]))
    if ref_year - 1 == ano_base:
        anos = [ano_base, ref_year]
    records = []
    for year in anos:
        lim = ref_month if year == ref_year else 12
        for month in range(1, lim + 1):
            start = f"{year}-{month:02d}-01"
            nm = month % 12 + 1
            ny = year + 1 if month == 12 else year
            end = f"{ny}-{nm:02d}-01"
            try:
                col = (ee.ImageCollection("MODIS/061/MOD11A2")
                       .filterDate(start, end)
                       .filterBounds(geom)
                       .map(modis_temperature)
                       .select("surface_temperature")
                       .mean())
                val = col.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=geom, scale=1000, maxPixels=1e13
                ).get("surface_temperature").getInfo()
                records.append({"ano": year, "mes": month,
                                 "temperatura": round(val, 2) if val else None})
            except:
                records.append({"ano": year, "mes": month, "temperatura": None})
    return pd.DataFrame(records)


def get_temp_latest_day(lake_name, asset_id, name_field="name"):
    """
    Retorna (temperatura, data_str) do ultimo dia com pixel valido
    no MOD11A1 para o lago especifico.
    Considera nuvens: busca os ultimos 30 dias e pega o mais recente
    que tenha reducao valida sobre a geometria do lago.
    """
    from datetime import datetime as _dt, timedelta
    now = _dt.utcnow()
    start_ee = ee.Date(
        (now - timedelta(days=30)).strftime("%Y-%m-%d"))
    end_ee = ee.Date(now.strftime("%Y-%m-%d"))

    feat = get_feature(lake_name, asset_id, name_field)
    geom_safe, _ = _safe_geometry(feat)

    col = (ee.ImageCollection("MODIS/061/MOD11A1")
           .filterDate(start_ee, end_ee)
           .filterBounds(geom_safe.bounds())
           .map(modis_temperature)
           .select("surface_temperature")
           .sort("system:time_start", False))

    def reduce_img(img):
        val = img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom_safe,
            scale=1000, maxPixels=1e13
        ).get("surface_temperature")
        return img.set("temp_val", val)

    col_red = col.map(reduce_img)
    # Filtra apenas imagens com pixel valido sobre o lago
    col_valid = col_red.filter(ee.Filter.notNull(["temp_val"]))

    try:
        n = col_valid.size().getInfo()
        if n == 0:
            return None, None
        # Pega o mais recente com dado valido
        latest = col_valid.sort("system:time_start", False).first()
        temp = latest.get("temp_val").getInfo()
        date_ts = latest.get("system:time_start").getInfo()
        date_obj = _dt.utcfromtimestamp(date_ts / 1000)
        # Formato: "10/Set/2026"
        meses_pt = ["Jan","Fev","Mar","Abr","Mai","Jun",
                    "Jul","Ago","Set","Out","Nov","Dez"]
        date_str = f"{date_obj.day:02d}/{meses_pt[date_obj.month-1]}/{date_obj.year}"
        return round(temp, 2) if temp else None, date_str
    except:
        return None, None

def get_temp_stats(name, asset_id, sel_year, sel_month, name_field="name"):
    """
    Retorna (t_atual_dia, t_prev, t_hist):
    - t_atual_dia: temperatura do DIA mais recente do MOD11A1
    - t_prev:      media do mesmo mes no ano anterior (MOD11A2)
    - t_hist:      media historica do mes (MOD11A2, ultimos 3 anos)
    """
    from datetime import datetime as _dt
    _now = _dt.utcnow()
    _cy, _cm = _now.year, _now.month

    feat = get_feature(name, asset_id, name_field)
    geom_safe, _ = _safe_geometry(feat)

    def get_temp_mensal(year, month):
        """Media mensal via MOD11A2."""
        start = f"{year}-{month:02d}-01"
        nm = month % 12 + 1
        ny = year + 1 if month == 12 else year
        end = f"{ny}-{nm:02d}-01"
        try:
            col = (ee.ImageCollection("MODIS/061/MOD11A2")
                   .filterDate(start, end)
                   .filterBounds(geom_safe.bounds())
                   .map(modis_temperature)
                   .select("surface_temperature").mean())
            val = col.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geom_safe, scale=1000, maxPixels=1e13
            ).get("surface_temperature").getInfo()
            return round(val, 2) if val else None
        except:
            return None

    # Para o mes atual: pega o dia mais recente do MOD11A1
    if sel_year == _cy and sel_month == _cm:
        t_atual, _ = get_temp_latest_day(name, asset_id, name_field)
    else:
        # Para meses anteriores: media mensal MOD11A2
        t_atual = get_temp_mensal(sel_year, sel_month)

    t_prev = get_temp_mensal(sel_year - 1, sel_month)
    hist = [get_temp_mensal(y, sel_month) for y in range(sel_year - 3, sel_year)]
    hist = [v for v in hist if v]
    t_hist = round(sum(hist) / len(hist), 2) if hist else None
    return t_atual, t_prev, t_hist

def get_focos_count_periodo(name, buffer_asset, dist_m, year, month,
                             name_field="name", dynamic=False, geom_src=None):
    """Conta focos num mes/ano. Se dynamic=True usa buffer calculado."""
    try:
        if dynamic and geom_src is not None:
            geom = geom_src.buffer(dist_m)
        else:
            buffers = ee.FeatureCollection(buffer_asset)
            geom = (buffers.filter(ee.Filter.eq("name", name))
                           .filter(ee.Filter.eq("dist_m", dist_m))
                           .geometry())
        start_ee = ee.Date.fromYMD(year, month, 1)
        end_ee   = start_ee.advance(1, "month")
        focos = ee.ImageCollection("NASA/LANCE/SNPP_VIIRS/C2").filterDate(start_ee, end_ee)
        if focos.size().getInfo() == 0:
            return 0
        def count_img(img):
            conf = img.select("confidence").gte(1).selfMask()
            n = conf.reduceRegion(
                reducer=ee.Reducer.count(),
                geometry=geom, scale=375, maxPixels=1e13, tileScale=2
            ).get("confidence")
            return img.set("count", ee.Algorithms.If(n, n, 0))
        total = focos.map(count_img).aggregate_sum("count").getInfo()
        return int(total) if total else 0
    except:
        return 0

def get_monthly_focos(name, buffer_asset, dist_m, ano_base, ref_year, ref_month,
                       name_field="name", dynamic=False, geom_src=None):
    """Focos mensais para anos: ano_base, ref_year-1, ref_year."""
    anos = sorted(set([ano_base, ref_year - 1, ref_year]))
    if ref_year - 1 == ano_base:
        anos = [ano_base, ref_year]
    records = []
    for year in anos:
        lim = ref_month if year == ref_year else 12
        for month in range(1, lim + 1):
            val = get_focos_count_periodo(
                name, buffer_asset, dist_m, year, month,
                name_field=name_field, dynamic=dynamic, geom_src=geom_src)
            records.append({"ano": year, "mes": month, "focos": val})
    return pd.DataFrame(records)

def get_ranking_temperatura(lagos, asset_id, sel_year, sel_month, name_field="name"):
    rows = []
    for name in lagos:
        try:
            t_a, t_p, t_h = get_temp_stats(name, asset_id, sel_year, sel_month, name_field)
            rows.append({
                "Lago": name,
                "Temp atual (C)":  round(t_a, 2) if t_a else None,
                "Media historica": round(t_h, 2) if t_h else None,
                f"Dif {sel_year-1}": round(t_a - t_p, 2) if t_a and t_p else None,
                "Dif media":       round(t_a - t_h, 2) if t_a and t_h else None,
            })
        except:
            rows.append({"Lago": name, "Temp atual (C)": None,
                         "Media historica": None,
                         f"Dif {sel_year-1}": None, "Dif media": None})
    return pd.DataFrame(rows)

def get_ranking_focos_periodo(lagos, buffer_asset, year, month,
                               dynamic_names=None, tocantins_asset=None):
    rows = []
    dynamic_names = dynamic_names or []
    for name in lagos:
        try:
            is_dynamic = name in dynamic_names
            geom_src = None
            if is_dynamic and tocantins_asset:
                feat = get_feature(name, tocantins_asset, "Name")
                geom_src = feat.geometry()
            f5  = get_focos_count_periodo(name, buffer_asset, 5000,  year, month,
                                           dynamic=is_dynamic, geom_src=geom_src)
            f10 = get_focos_count_periodo(name, buffer_asset, 10000, year, month,
                                           dynamic=is_dynamic, geom_src=geom_src)
            rows.append({"Lago": name, "Focos 5km": f5, "Focos 10km": f10})
        except:
            rows.append({"Lago": name, "Focos 5km": None, "Focos 10km": None})
    return pd.DataFrame(rows)



def get_all_lakes_temp_acumulado(lagos, asset_id, ano_base, ref_year, ref_month, name_field="name"):
    """
    Versao otimizada: usa ee.FeatureCollection.reduceColumns em batch.
    Uma unica chamada GEE por mes/ano em vez de uma por lago.
    Para 24 lagos x 8 meses x 3 anos = 576 chamadas -> ~24 chamadas.
    """
    import time

    fc = ee.FeatureCollection(asset_id)

    def mean_temp_all_lakes(year, month):
        """Retorna dict {name -> temp_media} para todos os lagos num mes/ano."""
        start = f"{year}-{month:02d}-01"
        nm = month % 12 + 1
        ny = year + 1 if month == 12 else year
        end = f"{ny}-{nm:02d}-01"
        col = (ee.ImageCollection("MODIS/061/MOD11A2")
               .filterDate(start, end)
               .map(modis_temperature)
               .select("surface_temperature")
               .mean())
        # Reduz sobre todos os lagos de uma vez
        def reduce_lake(feat):
            val = col.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=feat.geometry(),
                scale=1000, maxPixels=1e13
            ).get("surface_temperature")
            return feat.set("temp", val)
        result = fc.map(reduce_lake)
        names = result.aggregate_array(name_field).getInfo()
        temps = result.aggregate_array("temp").getInfo()
        return dict(zip(names, temps))

    # Busca centroides de todos os lagos de uma vez
    def get_centroids():
        def add_centroid(feat):
            c = feat.geometry().centroid()
            coords = c.coordinates()
            return feat.set("cx", coords.get(0)).set("cy", coords.get(1))
        result = fc.map(add_centroid)
        names = result.aggregate_array(name_field).getInfo()
        cxs   = result.aggregate_array("cx").getInfo()
        cys   = result.aggregate_array("cy").getInfo()
        return {n: [cx, cy] for n, cx, cy in zip(names, cxs, cys)}

    centroids = get_centroids()

    # Coleta temperaturas para cada mes/ano em batch
    # anos: ano_base, ref_year-1, ref_year
    anos = sorted(set([ano_base, ref_year - 1, ref_year]))
    if ref_year - 1 == ano_base:
        anos = [ano_base, ref_year]

    temps = {}  # {(year, month): {name: temp}}
    for year in anos:
        lim = ref_month if year == ref_year else 12
        for month in range(1, lim + 1):
            try:
                temps[(year, month)] = mean_temp_all_lakes(year, month)
            except:
                temps[(year, month)] = {}

    # Monta DataFrame com diferencas acumuladas
    rows = []
    for name in lagos:
        dif_base_total = 0.0
        dif_avg_total  = 0.0
        lim = ref_month

        for month in range(1, lim + 1):
            t_cur  = temps.get((ref_year, month), {}).get(name)
            t_base = temps.get((ano_base,  month), {}).get(name)

            # Media historica: media de todos os anos anteriores ao ref_year
            hist_vals = [
                temps.get((y, month), {}).get(name)
                for y in anos if y < ref_year
            ]
            hist_vals = [v for v in hist_vals if v]
            t_avg = sum(hist_vals) / len(hist_vals) if hist_vals else None

            if t_cur and t_base:
                dif_base_total += round(t_cur - t_base, 2)
            if t_cur and t_avg:
                dif_avg_total  += round(t_cur - t_avg, 2)

        # Centroide
        coord = centroids.get(name)
        rows.append({
            "Lago":     name,
            "dif_base": round(dif_base_total, 1),
            "dif_avg":  round(dif_avg_total,  1),
            "centroid": coord,
        })

    return pd.DataFrame(rows)

# ─────────────────────────────────────────────────────────────────
# ESTRATEGIA DE PRODUTO MODIS:
# - Mes atual:       MOD11A1 (diario)  → dado mais recente possivel
# - Meses anteriores: MOD11A2 (8 dias) → serie historica consistente
# As duas series NAO sao misturadas na mesma comparacao numerica.
# O mes atual aparece destacado nos graficos como "dado preliminar".
# ─────────────────────────────────────────────────────────────────

def get_modis_daily_tile(lake_name, asset_id, year, month, name_field="name"):
    """
    Tile MODIS diario (MOD11A1) para o mes atual.
    Mostra a composicao mediana de todos os dias disponiveis no mes.
    """
    feat = get_feature(lake_name, asset_id, name_field)
    _, bounds = _safe_geometry(feat)
    start = f"{year}-{month:02d}-01"
    nm = month % 12 + 1
    ny = year + 1 if month == 12 else year
    end = f"{ny}-{nm:02d}-01"
    col = (ee.ImageCollection("MODIS/061/MOD11A1")
           .filterDate(start, end)
           .filterBounds(bounds)
           .map(modis_temperature)
           .select("surface_temperature")
           .median())
    vis = {"min": "15", "max": "35", "palette": "blue,green,yellow,orange,red"}
    return get_tile_url(col, vis)

def get_daily_temperature_current_month(lake_name, asset_id, year, month,
                                         name_field="name"):
    """
    Busca temperatura diaria (MOD11A1) para cada dia disponivel
    no mes. Usa hoje como data final para garantir dados mais recentes.
    Retorna DataFrame com colunas: data, dia, temperatura.
    """
    from datetime import datetime as _dt
    feat = get_feature(lake_name, asset_id, name_field)
    geom_safe, _ = _safe_geometry(feat)

    start = f"{year}-{month:02d}-01"

    # Para o mes atual: usa hoje como fim para pegar todos os dias disponiveis
    now = _dt.utcnow()
    if year == now.year and month == now.month:
        # Avanca 1 dia para incluir hoje
        end = (now.replace(hour=23, minute=59)).strftime("%Y-%m-%d")
    else:
        nm = month % 12 + 1
        ny = year + 1 if month == 12 else year
        end = f"{ny}-{nm:02d}-01"

    col = (ee.ImageCollection("MODIS/061/MOD11A1")
           .filterDate(start, end)
           .filterBounds(geom_safe.bounds())
           .map(modis_temperature)
           .select("surface_temperature")
           .sort("system:time_start", True))  # ordena crescente por data

    def reduce_day(img):
        val = img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom_safe,
            scale=1000, maxPixels=1e13
        ).get("surface_temperature")
        date = img.date().format("YYYY-MM-dd")
        return img.set("temp", val).set("date_str", date)

    col_reduced = col.map(reduce_day)
    # Filtra apenas dias com pixel valido sobre o lago
    col_valid = col_reduced.filter(ee.Filter.notNull(["temp"]))

    dates = col_valid.aggregate_array("date_str").getInfo()
    temps = col_valid.aggregate_array("temp").getInfo()

    records = []
    for d, t in zip(dates, temps):
        if t is not None:
            records.append({
                "data": d,
                "dia":  int(d.split("-")[2]),
                "temperatura": round(t, 2)
            })
    return pd.DataFrame(records)

def get_monthly_temperature_hybrid(lake_name, asset_id, ano_base,
                                    ref_year, ref_month, name_field="name"):
    """
    Versao hibrida:
    - Meses anteriores ao mes atual: MOD11A2 (8 dias) — serie historica
    - Mes atual do ano atual:        MOD11A1 (diario) — dado mais recente
    Retorna DataFrame com coluna extra 'produto' indicando qual foi usado.
    """
    feat = get_feature(lake_name, asset_id, name_field)
    geom_safe, _ = _safe_geometry(feat)

    anos = sorted(set([ano_base, ref_year - 1, ref_year]))
    if ref_year - 1 == ano_base:
        anos = [ano_base, ref_year]

    records = []
    for year in anos:
        lim = ref_month if year == ref_year else 12
        for month in range(1, lim + 1):
            # Mes atual do ano atual: usa MOD11A1 diario
            is_current = (year == ref_year and month == ref_month)
            produto = "MOD11A1" if is_current else "MOD11A2"
            colecao = "MODIS/061/MOD11A1" if is_current else "MODIS/061/MOD11A2"

            start = f"{year}-{month:02d}-01"
            nm = month % 12 + 1
            ny = year + 1 if month == 12 else year
            end = f"{ny}-{nm:02d}-01"

            try:
                col = (ee.ImageCollection(colecao)
                       .filterDate(start, end)
                       .filterBounds(geom_safe.bounds())
                       .map(modis_temperature)
                       .select("surface_temperature")
                       .mean())
                val = col.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=geom_safe,
                    scale=1000, maxPixels=1e13
                ).get("surface_temperature").getInfo()
                records.append({
                    "ano": year, "mes": month,
                    "temperatura": round(val, 2) if val else None,
                    "produto": produto
                })
            except:
                records.append({
                    "ano": year, "mes": month,
                    "temperatura": None, "produto": produto
                })
    return pd.DataFrame(records)

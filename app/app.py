"""Localizador de fuentes de NOₓ en el Valle de México (POC, opción B).

Muestra resultados precalculados por scripts/pinn/invert.py y scripts/pinn/export_app.py.
No corre modelos.

Uso: .venv/bin/streamlit run app/app.py
"""
import json
from pathlib import Path

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

DATA = Path(__file__).resolve().parents[1] / "data/processed/app"
MODELOS = {"Lineal (puffs, transporte de referencia)": "lineal", "PINN (núcleo físico aprendido, pluma)": "pinn"}
NOMBRE_PERIODO = {"2023-11-01_2023-12-31": "nov–dic 2023", "2024-02-15_2024-05-31": "15 feb–31 may 2024"}

st.set_page_config(page_title="Localizador de fuentes de NOₓ", page_icon="🗺️", layout="wide")


@st.cache_data
def cargar():
    res = json.load(open(DATA / "resultados.json"))
    capas = {n: json.load(open(DATA / f"{n}.geojson")) for n in ("regiones", "estaciones", "carreteras", "candidatos")}
    return res, capas


def color_alfa(a):
    """Azul si la emisión inferida es menor que el inventario, rojo si es mayor."""
    t = max(-1.0, min(1.0, (a - 1) / 0.6))
    if t >= 0:
        return [255, int(235 - 160 * t), int(220 - 190 * t), 150]
    return [int(235 + 170 * t), int(235 + 110 * t), 255, 150]


res, capas = cargar()
meta = res["meta"]
REG, TIPOS = meta["regiones"], meta["tipos_dia"]
periodos = list(res["periodos"])

st.title("Localizador de fuentes de NOₓ — Valle de México")
st.caption("Prueba de concepto. Emisión vial por región y tipo de día, y fuentes grandes, inferidas de las estaciones "
           "de SIMAT y de TEMPO con física de transporte. Resultados precalculados; no es un pronóstico oficial.")

with st.sidebar:
    st.header("Opciones")
    per = st.selectbox("Periodo", periodos, format_func=lambda p: NOMBRE_PERIODO.get(p, p))
    mod_lbl = st.radio("Modelo de transporte", list(MODELOS))
    tipo = st.radio("Tipo de día", range(3), format_func=lambda i: TIPOS[i])
    st.divider()
    st.markdown("**Cómo leer el factor α**: 1 = igual al inventario 2018 repartido por calles; "
                "0.8 = 20 % menos; 1.3 = 30 % más. Las barras de error son IC 90 % por remuestreo de días.")

R = res["periodos"][per]
M = R[MODELOS[mod_lbl]]
alfa, ic = M["alfa"][tipo], M.get("boot", {}).get("alfa_ic90")
prior = R["prior_regiones"]

tab_cambios, tab_mapa, tab_reg, tab_cont, tab_modelo = st.tabs(
    ["Cambios de emisión", "Mapa", "Emisiones por región", "Contingencias 2024", "Modelo y confianza"])
nz = M.get("normalizado", {})
info = meta.get("infovial_dia_completo", {})


def ic_txt(ic):
    return f"IC 90 % {ic[0]:.2f}–{ic[1]:.2f}"


def totales_rango(R, d):
    """Rango del total vial entre los dos modelos de transporte (los totales dependen del modelo)."""
    v = [R[k]["total_vial"][d] for k in MODELOS.values() if k in R]
    return min(v), max(v)


with tab_cambios:
    st.markdown("**Salida principal: el índice de emisión normalizado por meteorología.** Divide el NOₓ observado "
                "entre el que el modelo predice con la emisión del inventario fija (solo cambia el clima). Si el índice "
                "cambia, cambió la emisión; si solo cambia la concentración, fue el clima. Pasó los placebos "
                "(2019, días falsos de contingencia) con un margen de ~±10 %.")
    if nz:
        c1, c2, c3 = st.columns(3)
        c1.metric("Domingo ÷ hábil (emisión)", f"{nz['domingo_habil']:.2f}", help=ic_txt(nz["domingo_habil_ic90"]))
        c1.caption(f"{ic_txt(nz['domingo_habil_ic90'])} · Infovial día completo {info.get('domingo', [0.65, 0.73])[0]:.2f}–"
                   f"{info.get('domingo', [0.65, 0.73])[1]:.2f}")
        c2.metric("Sábado ÷ hábil (emisión)", f"{nz['sabado_habil']:.2f}", help=ic_txt(nz["sabado_habil_ic90"]))
        c2.caption(f"{ic_txt(nz['sabado_habil_ic90'])} · Infovial día completo {info.get('sabado', [0.84, 0.89])[0]:.2f}–"
                   f"{info.get('sabado', [0.84, 0.89])[1]:.2f}")
        v20 = meta.get("validacion_2020", {}).get("did", {}).get("fase2/base|hábil")
        if v20:
            c3.metric("Confinamiento 2020 (fase 2, hábiles)", f"{(v20['estimado'] - 1) * 100:+.0f} %",
                      help=f"2020 ÷ 2019 (placebo), IC 90 % {v20['ic90'][0]:.2f}–{v20['ic90'][1]:.2f}")
            c3.caption(f"IC 90 % {(v20['ic90'][0] - 1) * 100:+.0f} a {(v20['ic90'][1] - 1) * 100:+.0f} %")
        tab = pd.DataFrame({"": ["Sábado ÷ hábil", "Domingo ÷ hábil"],
                            "Concentración observada": [nz["concentracion_sabado_habil"], nz["concentracion_domingo_habil"]],
                            "Efecto del clima (modelo fijo)": [nz["meteorologia_sabado_habil"], nz["meteorologia_domingo_habil"]],
                            "Índice de emisión": [nz["sabado_habil"], nz["domingo_habil"]],
                            "IC 90 %": [ic_txt(nz["sabado_habil_ic90"])[8:], ic_txt(nz["domingo_habil_ic90"])[8:]]})
        st.dataframe(tab.style.format(precision=2), hide_index=True, width="stretch")
    ct = meta.get("contingencias_2024", {}).get("grupos", {}).get("todos")
    if ct:
        st.info(f"Contingencias de ozono 2024 ({meta['contingencias_2024']['dias_contingencia']} días): índice de emisión "
                f"{ct['emision']:.2f} ({ic_txt(ct['ic90'])}), sin baja visible de NOₓ por la tarde. Detalle en la pestaña "
                "«Contingencias 2024».")
    st.subheader("Índice diario en el periodo")
    f = DATA / f"normalizado_{MODELOS[mod_lbl]}_{per}.parquet"
    if f.exists():
        d = pd.read_parquet(f)
        d["Tipo de día"] = d.tipo.map(dict(enumerate(TIPOS)))
        long = d.melt(id_vars=["dia", "Tipo de día"], value_vars=["obs_ppb", "modelo_ppb"], var_name="serie", value_name="ppb")
        long["serie"] = long.serie.map({"obs_ppb": "Observado", "modelo_ppb": "Modelo con emisión fija (solo clima)"})
        st.altair_chart(alt.Chart(long).mark_line(point=True).encode(x=alt.X("dia:T", title="Día"), y="ppb:Q",
                                                                     color="serie:N", tooltip=["dia:T", "serie:N", "ppb:Q"])
                        .properties(height=260), width="stretch")
        st.altair_chart(alt.Chart(d).mark_bar().encode(x=alt.X("dia:T", title="Día"), y=alt.Y("indice:Q", title="Índice de emisión"),
                                                       color=alt.Color("Tipo de día:N", sort=TIPOS), tooltip=["dia:T", "indice:Q"])
                        .properties(height=220), width="stretch")
    st.subheader("Todos los periodos")
    filas = []
    for p, Rp in res["periodos"].items():
        for lbl, k in MODELOS.items():
            n = Rp.get(k, {}).get("normalizado")
            if n:
                filas.append({"Periodo": NOMBRE_PERIODO.get(p, p), "Modelo": lbl, "Sábado ÷ hábil": n["sabado_habil"],
                              "IC sábado": ic_txt(n["sabado_habil_ic90"])[8:], "Domingo ÷ hábil": n["domingo_habil"],
                              "IC domingo": ic_txt(n["domingo_habil_ic90"])[8:]})
    st.dataframe(pd.DataFrame(filas).style.format(precision=2), hide_index=True, width="stretch")
    st.caption("Los cocientes de este estimador son estables entre modelos de transporte. Con TEMPO este estimador no pasa "
               "el placebo (reports/placebo_tempo.md): aquí solo se usan estaciones.")

with tab_mapa:
    reg = json.loads(json.dumps(capas["regiones"]))
    for f in reg["features"]:
        g = f["properties"]["region"]
        a = alfa[g]
        f["properties"].update(alfa=round(a, 2), color=color_alfa(a),
                               ic=f"{ic[tipo][g][0]:.2f}–{ic[tipo][g][1]:.2f}" if ic else "s/d",
                               emision=f"{a * prior[g]:,.0f}",
                               texto=f"Región {f['properties']['nombre']}")
    usadas = set(M.get("loo", {}).get("por_estacion", {}))
    est = json.loads(json.dumps(capas["estaciones"]))
    for f in est["features"]:
        s = f["properties"]["cve_estac"]
        loo = M.get("loo", {}).get("por_estacion", {}).get(s)
        f["properties"]["texto"] = f"Estación {s} ({f['properties'].get('nom_estac', '')})"
        f["properties"]["alfa"] = f"error al retenerla: {loo['rmse']:.0f} ppb" if loo else "sin NOₓ medido o fuera del ajuste"
        f["properties"]["ic"] = ""
        f["properties"]["emision"] = ""
        f["properties"]["color"] = [30, 30, 30, 230] if s in usadas else [140, 140, 140, 160]
    fuentes = dict(zip(R["fuentes"], zip(M["puntos"], M.get("puntos_sd", [0] * len(M["puntos"])), R["prior_puntos"])))
    cand = json.loads(json.dumps(capas["candidatos"]))
    cand["features"] = [f for f in cand["features"] if f["properties"]["nombre"] in fuentes]
    for f in cand["features"]:
        v, sd, pr = fuentes[f["properties"]["nombre"]]
        f["properties"].update(texto=f["properties"]["nombre"], alfa=f"{v:,.0f} ± {sd:,.0f} t/año (a priori {pr:,.0f})",
                               ic="", emision="", radio=300 + 6 * max(v, 0) ** 0.5 * 10)
    capas_pdk = [
        pdk.Layer("GeoJsonLayer", reg, filled=True, stroked=True, get_fill_color="properties.color",
                  get_line_color=[80, 80, 80], line_width_min_pixels=1, pickable=True),
        pdk.Layer("GeoJsonLayer", capas["carreteras"], stroked=True, filled=False, get_line_color=[90, 90, 90, 140],
                  line_width_min_pixels=1),
        pdk.Layer("GeoJsonLayer", est, point_type="circle", get_fill_color="properties.color", get_point_radius=500,
                  pickable=True),
        pdk.Layer("GeoJsonLayer", cand, point_type="circle", get_fill_color=[200, 0, 120, 220],
                  get_point_radius="properties.radio", pickable=True),
    ]
    tip = {"html": "<b>{texto}</b><br/>{alfa}<br/>{ic}<br/>{emision}", "style": {"fontSize": "12px"}}
    st.pydeck_chart(pdk.Deck(layers=capas_pdk, initial_view_state=pdk.ViewState(latitude=19.51, longitude=-99.08, zoom=9),
                             tooltip=tip, map_style=None), height=620)
    st.caption("Color de región: α para el tipo de día elegido (azul < 1 < rojo). Puntos negros: estaciones de NOₓ usadas; "
               "grises: sin NOₓ. Círculos magenta: fuentes grandes (tamaño ∝ emisión inferida). Líneas: vías primarias.")

with tab_reg:
    filas = []
    for d in range(3):
        for g in range(len(REG)):
            lo, hi = (ic[d][g] if ic else (None, None))
            filas.append({"Región": REG[g], "Tipo de día": TIPOS[d], "α": M["alfa"][d][g], "IC bajo": lo, "IC alto": hi,
                          "Emisión (t/año eq.)": M["alfa"][d][g] * prior[g]})
    df = pd.DataFrame(filas)
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Factor α por región")
        base = alt.Chart(df).encode(x=alt.X("Región:N", sort=REG), xOffset="Tipo de día:N",
                                    color=alt.Color("Tipo de día:N", sort=TIPOS))
        ch = base.mark_bar().encode(y=alt.Y("α:Q", title="α (1 = inventario)")) + \
            base.mark_rule(color="black").encode(y="IC bajo:Q", y2="IC alto:Q")
        st.altair_chart((ch + alt.Chart(pd.DataFrame({"y": [1]})).mark_rule(strokeDash=[4, 4]).encode(y="y:Q"))
                        .properties(height=360), width="stretch")
    with c2:
        st.subheader("Total vial por tipo de día")
        lo0, hi0 = totales_rango(R, 0)
        st.warning(f"Los totales absolutos dependen del modelo de transporte: en este periodo el lineal (puffs) y la PINN "
                   f"(pluma) difieren {hi0 / lo0 - 1:.0%} en el total de día hábil. "
                   "Úselos como orden de magnitud; los cambios relativos están en «Cambios de emisión».")
        b = M.get("boot", {})
        tot = pd.DataFrame({"Tipo de día": TIPOS, "Total (t/año eq.)": M["total_vial"],
                            "IC 90 % (este modelo)": [f"{a:,.0f}–{z:,.0f}" for a, z in b.get("total_vial_ic90", [[0, 0]] * 3)],
                            "Rango lineal–PINN": [f"{a:,.0f}–{z:,.0f}" for a, z in (totales_rango(R, d) for d in range(3))]})
        st.dataframe(tot.style.format({"Total (t/año eq.)": "{:,.0f}"}), hide_index=True, width="stretch")
        rc = R.get("restriccion_cociente")
        if rc:
            st.caption(f"Los cocientes por tipo de día de la inversión están atados al tráfico de Infovial (sábado "
                       f"{rc['sabado'][0]:.2f}, rango {rc['rango_sabado'][0]:.2f}–{rc['rango_sabado'][1]:.2f}; domingo {rc['domingo'][0]:.2f}, "
                       f"rango {rc['rango_domingo'][0]:.2f}–{rc['rango_domingo'][1]:.2f}): "
                       f"las estaciones no los determinan (reports/sesgo_domingos.md). Inversión: sábado "
                       f"{M['cociente_sabado']:.2f}, domingo {M['cociente_domingo']:.2f}. Lo que sí sale de los datos es el "
                       "reparto entre regiones.")
    st.subheader("Fuentes grandes")
    st.dataframe(pd.DataFrame({"Fuente": R["fuentes"], "A priori (t/año)": R["prior_puntos"], "Inferida (t/año)": M["puntos"],
                               "± (1σ)": M.get("puntos_sd", [None] * len(M["puntos"]))})
                 .style.format(precision=0, thousands=","), hide_index=True, width="stretch")
    st.caption("Los aeropuertos (AICM, AIFA) son inestables entre configuraciones: tomarlos como indicativos.")

with tab_cont:
    C = meta.get("contingencias_2024", {})
    if not C:
        st.write("Sin datos de contingencias (correr scripts/contingencias_2024.py y scripts/pinn/export_app.py).")
    else:
        st.markdown("**¿Bajó la emisión de NOₓ en los días de contingencia ambiental de ozono de 2024?** Se compara cada "
                    "día de contingencia contra días del mismo tipo en semanas cercanas sin contingencia, por la tarde "
                    "(12–17 h), con el índice normalizado por meteorología. Fechas tomadas de prensa: falta confirmarlas "
                    "con los comunicados de la CAMe.")
        g = C["grupos"]
        filas = [{"Grupo": k, "Días": v["dias"], "Concentración": v["concentracion"], "Efecto del clima": v["meteorologia"],
                  "Índice de emisión": v["emision"], "IC 90 %": f"{v['ic90'][0]:.2f}–{v['ic90'][1]:.2f}"} for k, v in g.items()]
        C1 = meta.get("contingencias_2024_dia_siguiente", {}).get("grupos", {}).get("todos")
        if C1:
            filas.append({"Grupo": "todos (restricción al día siguiente)", "Días": C1["dias"], "Concentración": C1["concentracion"],
                          "Efecto del clima": C1["meteorologia"], "Índice de emisión": C1["emision"],
                          "IC 90 %": f"{C1['ic90'][0]:.2f}–{C1['ic90'][1]:.2f}"})
        st.dataframe(pd.DataFrame(filas).style.format(precision=2), hide_index=True, width="stretch")
        pl = C.get("placebos", {})
        if pl:
            st.subheader("Placebos: días falsos de contingencia")
            st.dataframe(pd.DataFrame([{"Placebo": k.replace("|", ", "), "Mediana": v["mediana"], "p5": v["p5"], "p95": v["p95"]}
                                       for k, v in pl.items()]).style.format(precision=2), hide_index=True, width="stretch")
            st.caption("Sin efecto real, el índice da 0.90–0.98 con un margen de ~±10 %: una baja de emisión de 10–15 % o "
                       "más se habría detectado. El índice > 1 en contingencias refleja un sesgo de los episodios "
                       "(acumulación de varios días o fondo regional), no más emisión.")
        st.subheader("Por episodio")
        st.dataframe(pd.DataFrame([{"Fechas": e["fechas"], "Días": e["dias"], "Concentración": e["concentracion"],
                                    "Efecto del clima": e["meteorologia"], "Índice de emisión": e["emision"],
                                    "IC 90 %": f"{e['ic90'][0]:.2f}–{e['ic90'][1]:.2f}", "O₃ máx (ppb)": e["o3max"]}
                                   for e in C["episodios"]]).style.format(precision=2), hide_index=True, width="stretch")
        f = DATA / "contingencias_2024_diario.parquet"
        if f.exists():
            d = pd.read_parquet(f)
            d["Día"] = d.contingencia.map({True: "Contingencia", False: "Sin contingencia"})
            st.altair_chart(alt.Chart(d).mark_bar().encode(
                x=alt.X("dia:T", title="Día"), y=alt.Y("indice:Q", title="Índice de emisión (tarde)"),
                color=alt.Color("Día:N", scale=alt.Scale(domain=["Sin contingencia", "Contingencia"], range=["#9aa5b1", "#d1495b"])),
                tooltip=["dia:T", "indice:Q", "obs_ppb:Q", "modelo_ppb:Q"]).properties(height=260), width="stretch")
    v = meta.get("validacion_2020", {})
    if v:
        st.subheader("Referencia: confinamiento 2020 (con 2019 como placebo)")
        filas = []
        for k in ("fase2/base|hábil", "fase3/base|hábil"):
            filas.append({"Comparación": k.replace("|", ", "), "2020": v["2020"][k]["estimado"], "2019 placebo": v["2019"][k]["estimado"],
                          "2020 ÷ 2019": v["did"][k]["estimado"],
                          "IC 90 % (2020 ÷ 2019)": f"{v['did'][k]['ic90'][0]:.2f}–{v['did'][k]['ic90'][1]:.2f}"})
        st.dataframe(pd.DataFrame(filas).style.format(precision=2), hide_index=True, width="stretch")
        st.caption("El placebo 2019 da ≈ 1 (sin cambio, correcto) y 2020 da una baja de ~35 % de la emisión vial: "
                   "una medida grande sí se ve.")

with tab_modelo:
    st.subheader("Lineal vs PINN en este periodo")
    rows = []
    variantes = [(lbl, k) for lbl, k in MODELOS.items()] + \
        [(lbl + ", sin restricción de cociente", k + "_sin_restriccion") for lbl, k in MODELOS.items() if k + "_sin_restriccion" in R]
    for lbl, k in variantes:
        m = R[k]
        rows.append({"Modelo": lbl, "Total vial hábil (t/año)": m["total_vial"][0], "Sábado ÷ hábil": m["cociente_sabado"],
                     "Domingo ÷ hábil": m["cociente_domingo"], "r estaciones": m["ajuste_estaciones"]["r"],
                     "RMSE estaciones (ppb)": m["ajuste_estaciones"]["rmse"],
                     "RMSE estación retenida (ppb)": m.get("loo", {}).get("rmse_ponderado"), "r TEMPO": m.get("ajuste_tempo_r")})
    st.dataframe(pd.DataFrame(rows).style.format(precision=2, thousands=","), hide_index=True, width="stretch")
    st.caption("La restricción de cociente (Infovial) apenas cambia el ajuste ni el error con estación retenida: "
               "los datos no distinguen entre cocientes, así que se usa el tráfico medido.")
    if "gemelo" in R:
        st.subheader("Experimento gemelo (emisiones conocidas)")
        g = R["gemelo"]
        st.dataframe(pd.DataFrame([{"Datos simulados con → invertido con": k, "Error total vial (hábil)": v["err_total_mediano_por_tipo"][0],
                                    "Error domingo÷hábil": v["err_cociente_domingo_mediano"], "Error α mediano": v["err_alfa_mediano"]}
                                   for k, v in g.items()]).style.format(precision=2), hide_index=True, width="stretch")
        st.caption("Errores relativos medianos. Cruzar modelos (lineal→PINN o PINN→lineal) mide cuánto cuesta equivocarse de física.")
    nuc = meta.get("nucleo", {}).get("validacion")
    if nuc:
        st.subheader("La red contra la solución exacta")
        st.dataframe(pd.DataFrame([{"γ": k, "Error relativo mediano": v["err_rel_mediano"], "Error p90": v["err_rel_p90"],
                                    "Error de masa": v["err_masa"]} for k, v in nuc.items()]).style.format(precision=3),
                     hide_index=True, width="stretch")
    st.markdown("Detalle en `reports/pinn_prototipo.md`.")

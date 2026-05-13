"""revenue.py — ingresos plurianuales (ABAST + mayorista).

ABAST: 1.000 €/mes por sede conectada (alta gratis, 0 €).
Mayorista: 1.500 € de alta + 700 €/mes por sede mayorista activa.

La conexión es gradual según el plan de despliegue (vía
`capex._deployment_schedule`) y la rampa de cuota α(t)
(vía `capex._alpha`).

Funciones públicas:
    compute_revenue(df, decisiones, parametros) -> pd.DataFrame
"""

from __future__ import annotations

import logging

import pandas as pd

from src.capex import _alpha, _deployment_schedule

logger = logging.getLogger(__name__)

_N_ANIOS = 20


def compute_revenue(
    df: pd.DataFrame,
    decisiones: dict,
    parametros: dict,
) -> pd.DataFrame:
    """Calcula los ingresos plurianuales.

    Columnas de salida:
        anio, sedes_abast_activas, sedes_mayorista_activas,
        ingresos_abast_eur, ingresos_mayo_alta_eur,
        ingresos_mayo_rec_eur, total_eur

    Lógica:
    - ABAST: cuando un municipio conecta en el año Y, sus sedes_abast
      quedan activas de forma permanente. Ingreso = activas × 1.000 €/mes
      × 12 meses. Alta ABAST = 0 €.
    - Mayorista: sedes_mayo(muni, anio) = num_operadores × alpha(anio) ×
      penetracion_fibra (valor continuo). Nuevas altas = sedes que se
      incorporan ese año (por conexión nueva o por incremento de rampa).
      Alta = nuevas × 1.500 €. Recurrente = sedes_activas × 700 €/mes × 12.

    Args:
        df: DataFrame de topología.
        decisiones: configuración del escenario.
        parametros: tarifas (alta/recurrente ABAST y mayorista).

    Returns:
        DataFrame de 20 filas.
    """
    # ---- tarifas ----
    ing = parametros["ingresos"]
    rec_abast_mes = float(ing["recurrente_abast"])       # 1.000 €/mes
    alta_mayo_eur = float(ing["alta_mayorista"])          # 1.500 €/alta
    rec_mayo_mes = float(ing["recurrente_mayorista"])     # 700 €/mes

    # ---- mayorista params ----
    mayo_cfg = decisiones["mayorista"]["cuota_mercado"]
    alpha_obj = float(mayo_cfg["alpha_objetivo"])
    anios_rampa = int(mayo_cfg.get("anios_rampa", 8))
    penetracion = float(decisiones["mayorista"].get("penetracion_fibra_pct", 0.70))

    # ---- schedule ----
    schedule = _deployment_schedule(df, decisiones)

    # ---- topología acceso ----
    df_acc = df[df["tier"] == "acceso"].set_index("municipio")

    # Sedes de nodos de agregación y troncal — activos desde año 1 (infra ya construida)
    sedes_no_acceso = int(
        df[df["tier"].isin(["agregacion", "troncal"])]["sedes_abast"].sum()
    )
    # Para mayorista de nodos no-acceso: precompute sedes_mayo por municipio
    df_no_acc = df[df["tier"].isin(["agregacion", "troncal"])].set_index("municipio")

    # Acumuladores — iniciamos con sedes de nodos de agregacion/troncal
    sedes_abast_activas = sedes_no_acceso
    sedes_mayo_activas = 0.0
    sedes_mayo_por_muni: dict[str, float] = {}

    rows = []
    for anio in range(1, _N_ANIOS + 1):
        new_munis = [m for m, y in schedule.items() if y == anio]

        alpha_ahora = _alpha(anio, alpha_obj, anios_rampa)
        alpha_antes = _alpha(anio - 1, alpha_obj, anios_rampa)

        # ABAST: nuevas sedes de municipios que conectan
        nuevas_sedes_abast = sum(
            int(df_acc.loc[m, "sedes_abast"])
            for m in new_munis
            if m in df_acc.index
        )
        sedes_abast_activas += nuevas_sedes_abast

        # Mayorista: nuevas altas (conexiones nuevas + incremento rampa)
        nuevas_altas_mayo = 0.0

        # En año 1: incorporar nodos agregacion/troncal (ya conectados desde el inicio)
        if anio == 1:
            for m, row_no_acc in df_no_acc.iterrows():
                n_op = int(row_no_acc["num_operadores"])
                sedes_m = n_op * alpha_ahora * penetracion
                sedes_mayo_por_muni[str(m)] = sedes_m
                nuevas_altas_mayo += sedes_m

        # Municipios de acceso que conectan este año
        for m in new_munis:
            if m not in df_acc.index:
                continue
            n_op = int(df_acc.loc[m, "num_operadores"])
            sedes_m = n_op * alpha_ahora * penetracion
            sedes_mayo_por_muni[m] = sedes_m
            nuevas_altas_mayo += sedes_m

        # Todos los municipios ya activos (acceso previo + no-acceso): incremento de rampa
        already_active_acc = [m for m, y in schedule.items() if y < anio]
        for m in already_active_acc:
            if m not in df_acc.index:
                continue
            n_op = int(df_acc.loc[m, "num_operadores"])
            sedes_ahora_m = n_op * alpha_ahora * penetracion
            sedes_antes_m = sedes_mayo_por_muni.get(
                m, n_op * alpha_antes * penetracion
            )
            incremento = max(sedes_ahora_m - sedes_antes_m, 0.0)
            nuevas_altas_mayo += incremento
            sedes_mayo_por_muni[m] = sedes_ahora_m

        # No-acceso: incremento de rampa (anio > 1)
        if anio > 1:
            for m, row_no_acc in df_no_acc.iterrows():
                ms = str(m)
                n_op = int(row_no_acc["num_operadores"])
                sedes_ahora_m = n_op * alpha_ahora * penetracion
                sedes_antes_m = sedes_mayo_por_muni.get(
                    ms, n_op * alpha_antes * penetracion
                )
                incremento = max(sedes_ahora_m - sedes_antes_m, 0.0)
                nuevas_altas_mayo += incremento
                sedes_mayo_por_muni[ms] = sedes_ahora_m

        sedes_mayo_activas = sum(sedes_mayo_por_muni.values())

        # Ingresos
        ing_abast = sedes_abast_activas * rec_abast_mes * 12
        ing_mayo_alta = nuevas_altas_mayo * alta_mayo_eur
        ing_mayo_rec = sedes_mayo_activas * rec_mayo_mes * 12
        total = ing_abast + ing_mayo_alta + ing_mayo_rec

        rows.append({
            "anio": anio,
            "sedes_abast_activas": sedes_abast_activas,
            "sedes_mayorista_activas": round(sedes_mayo_activas, 2),
            "ingresos_abast_eur": round(ing_abast),
            "ingresos_mayo_alta_eur": round(ing_mayo_alta),
            "ingresos_mayo_rec_eur": round(ing_mayo_rec),
            "total_eur": round(total),
        })

    revenue_df = pd.DataFrame(rows)

    logger.info(
        "compute_revenue: ingresos año 20 = %.2f M€ "
        "(ABAST=%.1f M€, mayo_rec=%.1f M€, mayo_alta=%.1f M€); "
        "sedes_abast_activas=%d, sedes_mayo=%.0f",
        revenue_df.iloc[-1]["total_eur"] / 1e6,
        revenue_df.iloc[-1]["ingresos_abast_eur"] / 1e6,
        revenue_df.iloc[-1]["ingresos_mayo_rec_eur"] / 1e6,
        revenue_df.iloc[-1]["ingresos_mayo_alta_eur"] / 1e6,
        revenue_df.iloc[-1]["sedes_abast_activas"],
        revenue_df.iloc[-1]["sedes_mayorista_activas"],
    )
    return revenue_df

"""geomarketing.py — análisis de viabilidad y orden de despliegue por municipio.

Produce, para los 900 municipios:
    - Ingresos potenciales (ABAST + mayorista residencial + PYMEs).
    - CAPEX local estimado (obra civil + altas + punto de acceso).
    - OPEX local anual.
    - Payback municipal estimado.
    - Score de atractivo combinado (0-100).
    - Flag de viabilidad (informativo: la cobertura es obligatoria al 100%).

Y dos productos derivados:
    - `deployment_priority_order`: orden óptimo de despliegue.
    - `pyme_estimation_per_municipality`: PYMEs como segmento adicional.
    - `infraestructura_acceso_por_municipio`: armario de calle vs local cerrado.

API pública (ver `src/prompts/03b_geomarketing.md`):
    municipal_viability(df_topology, df_abast, df_mayo, parametros, decisiones)
    deployment_priority_order(df_viability, decisiones)
    pyme_estimation_per_municipality(df_topology, decisiones)
    infraestructura_acceso_por_municipio(df_topology, decisiones)
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd

from src.traffic import _cuota_alpha

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# pyme_estimation_per_municipality
# ---------------------------------------------------------------------------

def pyme_estimation_per_municipality(
    df_topology: pd.DataFrame,
    decisiones: dict,
) -> pd.DataFrame:
    """PYMEs por municipio (segmento adicional al residencial).

    Fórmula:
        n_pymes = hab / habitantes_por_pyme
        clientes_pyme = n_pymes × penetracion_pyme_pct
        bw_pyme_mbps = clientes_pyme × bw_por_pyme_mbps / overbooking_empresa

    Args:
        df_topology: DataFrame de `load.load_topology`.
        decisiones: configuración del escenario.

    Returns:
        DataFrame con columnas: codigo, n_pymes_estimadas, clientes_pyme,
        bw_pyme_mbps.
    """
    geo_cfg = decisiones["geomarketing"]["modelo_pymes"]
    hab_por_pyme = float(geo_cfg["habitantes_por_pyme"])
    bw_por_pyme = float(geo_cfg["bw_por_pyme_mbps"])
    penetracion_pyme = float(geo_cfg["penetracion_pyme_pct"])
    overbooking_empresa = float(
        decisiones["mayorista"].get("overbooking_empresa", 5)
    ) or 1.0

    out = df_topology[["codigo", "hab"]].copy()
    out["n_pymes_estimadas"] = out["hab"].astype(float) / hab_por_pyme
    out["clientes_pyme"] = out["n_pymes_estimadas"] * penetracion_pyme
    out["bw_pyme_mbps"] = out["clientes_pyme"] * bw_por_pyme / overbooking_empresa
    return out.drop(columns=["hab"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# infraestructura_acceso_por_municipio
# ---------------------------------------------------------------------------

def infraestructura_acceso_por_municipio(
    df_topology: pd.DataFrame,
    decisiones: dict,
) -> pd.DataFrame:
    """Decide armario de calle vs local cerrado para cada municipio.

    Reglas según `decisiones['infraestructura_acceso']['tipo_punto_acceso']`:
        - 'armario_calle' → todos los munis: CAPEX = coste_licencia_armario
        - 'local_cerrado' → todos los munis: OPEX = alquiler_local_anual
        - 'mixto'         → hab >= umbral → local; hab < umbral → armario

    El bloque sólo aplica a municipios de acceso (tier == 'acceso'). Los
    nodos de agregación/troncal no necesitan punto de acceso porque no
    venden servicio final.

    Args:
        df_topology: DataFrame con columnas codigo, hab, tier.
        decisiones: configuración del escenario.

    Returns:
        DataFrame: codigo, tipo_punto_acceso, capex_extra, opex_extra_anual.
    """
    cfg = decisiones["infraestructura_acceso"]
    tipo = cfg["tipo_punto_acceso"]
    coste_armario = float(cfg["coste_licencia_armario_eur"])
    alquiler_local = float(cfg["coste_alquiler_local_anual_eur"])
    umbral_local = float(cfg.get("umbral_hab_para_local_cerrado", 0))

    out = df_topology[["codigo", "hab", "tier"]].copy()

    if tipo == "armario_calle":
        out["tipo_punto_acceso"] = "armario_calle"
        out["capex_extra"] = coste_armario
        out["opex_extra_anual"] = 0.0
    elif tipo == "local_cerrado":
        out["tipo_punto_acceso"] = "local_cerrado"
        out["capex_extra"] = 0.0
        out["opex_extra_anual"] = alquiler_local
    elif tipo == "mixto":
        is_local = out["hab"] >= umbral_local
        out["tipo_punto_acceso"] = np.where(is_local, "local_cerrado", "armario_calle")
        out["capex_extra"] = np.where(is_local, 0.0, coste_armario)
        out["opex_extra_anual"] = np.where(is_local, alquiler_local, 0.0)
    else:
        raise ValueError(
            f"tipo_punto_acceso desconocido: {tipo!r} "
            "(esperado: armario_calle | local_cerrado | mixto)"
        )

    # Para nodos de agregación/troncal no aplica.
    is_no_access = out["tier"] != "acceso"
    out.loc[is_no_access, "tipo_punto_acceso"] = "no_aplica"
    out.loc[is_no_access, "capex_extra"] = 0.0
    out.loc[is_no_access, "opex_extra_anual"] = 0.0

    return out.drop(columns=["hab", "tier"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# municipal_viability
# ---------------------------------------------------------------------------

def municipal_viability(
    df_topology: pd.DataFrame,
    df_traffic_abast: pd.DataFrame,
    df_traffic_mayorista: pd.DataFrame,
    parametros: dict,
    decisiones: dict,
) -> pd.DataFrame:
    """Viabilidad económica por municipio en régimen estacionario.

    Calcula para cada municipio:
        - Ingresos anuales potenciales (ABAST + mayorista resi + PYMEs).
        - CAPEX local estimado (obra civil interna + altas + punto acceso).
        - OPEX local anual estimado (mantenimiento fibra interna + punto acceso).
        - Payback municipal (ignorando red troncal/agregación, sólo acceso).
        - Score de atractivo combinado (0..100).
        - Flag `viable` (cumple umbrales de viabilidad_minima).

    Para `cuota_operadores` aplica estrategia 'equilibrio' = 1/(num_op+1) en
    régimen estacionario, ignorando rampa temporal — el más conservador.

    Args:
        df_topology: DataFrame de `load.load_topology`.
        df_traffic_abast: salida de `traffic.traffic_abast`.
        df_traffic_mayorista: salida de `traffic.traffic_mayorista` (año 20).
        parametros: dict de `load.load_parameters` (tarifas, capex unitarios).
        decisiones: configuración del escenario.

    Returns:
        DataFrame: codigo, municipio, hab, sedes_abast, num_operadores,
        ingresos_abast_anuales, ingresos_mayorista_resi_anuales,
        ingresos_pymes_anuales, ingresos_total_anuales,
        capex_local_estimado, opex_local_anual,
        payback_municipal_anios, score_atractivo, viable.
    """
    # ---- tarifas y unitarios ----
    tarifa_abast_mes = float(parametros["ingresos"]["recurrente_abast"])
    tarifa_resi_mes = float(parametros["ingresos"]["recurrente_mayorista"])
    tarifa_pyme_mes = 2.0 * tarifa_resi_mes  # convención del prompt
    capex_alta_abast = float(parametros["capex"]["alta_sede_abast"])
    capex_alta_mayo = float(parametros["capex"]["alta_sede_mayorista"])
    obra_civil_acceso_eur_m = float(parametros["capex"]["obra_civil_acceso_eur_m"])
    mant_fibra_eur_km_año = float(parametros["opex"]["mant_fibra_eur_km_año"])

    # ---- decisiones residencial ----
    hab_por_hogar = float(decisiones["mayorista"]["habitantes_por_hogar"])
    penetracion = float(decisiones["mayorista"].get("penetracion_fibra_pct", 1.0))

    # ---- decisiones PYME ----
    pyme_cfg = decisiones["geomarketing"]["modelo_pymes"]
    hab_por_pyme = float(pyme_cfg["habitantes_por_pyme"])
    penetracion_pyme = float(pyme_cfg["penetracion_pyme_pct"])

    # ---- umbrales de viabilidad ----
    via_cfg = decisiones["geomarketing"]["viabilidad_minima"]
    ingresos_min = float(via_cfg["ingresos_anuales_min_eur"])
    payback_max = float(via_cfg["payback_municipal_max_anios"])

    # ---- punto de acceso por municipio (CAPEX + OPEX) ----
    df_infra = infraestructura_acceso_por_municipio(df_topology, decisiones)

    # ---- merge base ----
    df = df_topology[
        ["codigo", "municipio", "hab", "sedes_abast", "num_operadores", "km", "tier"]
    ].copy()
    df = df.merge(df_infra, on="codigo", how="left")

    # ---- ingresos ABAST ----
    df["ingresos_abast_anuales"] = (
        df["sedes_abast"].astype(float) * tarifa_abast_mes * 12
    )

    # ---- clientes residenciales (cuota_equilibrio = 1/(n+1)) ----
    df["hogares_teoricos"] = df["hab"].astype(float) / hab_por_hogar
    df["cuota_equilibrio"] = 1.0 / (df["num_operadores"].astype(float) + 1.0)
    df["clientes_resi"] = (
        df["hogares_teoricos"] * df["cuota_equilibrio"] * penetracion
    )
    df["ingresos_mayorista_resi_anuales"] = (
        df["clientes_resi"] * tarifa_resi_mes * 12
    )

    # ---- clientes PYME ----
    df["clientes_pyme"] = (
        df["hab"].astype(float) / hab_por_pyme * penetracion_pyme
    )
    df["ingresos_pymes_anuales"] = (
        df["clientes_pyme"] * tarifa_pyme_mes * 12
    )

    df["ingresos_total_anuales"] = (
        df["ingresos_abast_anuales"]
        + df["ingresos_mayorista_resi_anuales"]
        + df["ingresos_pymes_anuales"]
    )

    # ---- CAPEX local ----
    # Obra civil interna estimada: km al destino_acceso × factor 1.5 para
    # representar la red interna del muni (estimación grosera defendible).
    km_internos = df["km"].astype(float) * 1.5
    df["capex_obra_civil_local"] = km_internos * 1000.0 * obra_civil_acceso_eur_m
    df["capex_altas"] = (
        df["sedes_abast"].astype(float) * capex_alta_abast
        + df["clientes_resi"] * capex_alta_mayo
        + df["clientes_pyme"] * capex_alta_mayo
    )
    df["capex_local_estimado"] = (
        df["capex_obra_civil_local"]
        + df["capex_altas"]
        + df["capex_extra"]
    )

    # ---- OPEX local ----
    df["opex_local_anual"] = (
        km_internos * mant_fibra_eur_km_año
        + df["opex_extra_anual"]
    )

    # ---- payback municipal ----
    margen_anual = df["ingresos_total_anuales"] - df["opex_local_anual"]
    payback = np.where(
        margen_anual > 0,
        df["capex_local_estimado"] / margen_anual,
        np.inf,
    )
    df["payback_municipal_anios"] = payback

    # ---- score de atractivo (0..100) ----
    df["score_atractivo"] = _compute_score(df)

    # ---- flag viable ----
    df["viable"] = (
        (df["ingresos_total_anuales"] >= ingresos_min)
        & (df["payback_municipal_anios"] <= payback_max)
    )

    cols_out = [
        "codigo", "municipio", "hab", "sedes_abast", "num_operadores",
        "ingresos_abast_anuales", "ingresos_mayorista_resi_anuales",
        "ingresos_pymes_anuales", "ingresos_total_anuales",
        "capex_local_estimado", "opex_local_anual",
        "payback_municipal_anios", "score_atractivo", "viable",
    ]
    out = df[cols_out].reset_index(drop=True)

    n_viables = int(out["viable"].sum())
    logger.info(
        "municipal_viability: %d/%d municipios viables (ingresos_min=%.0f €, "
        "payback_max=%.1f años). Ingresos potenciales totales=%.1f M€/año.",
        n_viables, len(out), ingresos_min, payback_max,
        out["ingresos_total_anuales"].sum() / 1e6,
    )
    return out


def _compute_score(df: pd.DataFrame) -> pd.Series:
    """Score de atractivo combinado normalizado 0..100.

    Pesos:
        - 50% ingresos potenciales (mayor → mejor)
        - 30% payback corto (menor → mejor, invertido)
        - 10% densidad PYMEs ≈ clientes_pyme (mayor → mejor)
        - 10% baja competencia ≈ 1 / num_operadores (mayor → mejor)
    """
    def norm(s: pd.Series) -> pd.Series:
        s = s.replace([np.inf, -np.inf], np.nan)
        s = s.fillna(s.min())
        s_min, s_max = s.min(), s.max()
        if math.isclose(s_min, s_max):
            return pd.Series(np.zeros(len(s)), index=s.index)
        return (s - s_min) / (s_max - s_min)

    n_ing = norm(df["ingresos_total_anuales"])
    # Para payback usamos -payback (corto = score alto).
    n_pay = norm(-df["payback_municipal_anios"])
    n_pyme = norm(df["clientes_pyme"])
    n_comp = norm(1.0 / df["num_operadores"].astype(float).clip(lower=1))

    score = 0.5 * n_ing + 0.3 * n_pay + 0.1 * n_pyme + 0.1 * n_comp
    return (score * 100).round(2)


# ---------------------------------------------------------------------------
# deployment_priority_order
# ---------------------------------------------------------------------------

_CRITERIO_TO_COLUMN: dict[str, tuple[str, str]] = {
    # criterio_yaml -> (columna_en_df_viability, dirección)
    "ingresos_potenciales_descendente": ("ingresos_total_anuales", "desc"),
    "sedes_descendente":                ("sedes_abast", "desc"),
    "hab_descendente":                  ("hab", "desc"),
    "score_descendente":                ("score_atractivo", "desc"),
    "payback_ascendente":               ("payback_municipal_anios", "asc"),
}


def deployment_priority_order(
    df_viability: pd.DataFrame,
    decisiones: dict,
) -> pd.DataFrame:
    """Determina el orden de despliegue de municipios según el criterio elegido.

    Args:
        df_viability: salida de `municipal_viability`.
        decisiones: configuración del escenario. Lee
            `decisiones['geomarketing']['prioridad_despliegue']['criterio']`.

    Returns:
        DataFrame ordenado: orden_despliegue (1=primero), codigo, municipio,
        criterio_valor, anio_objetivo_despliegue.
    """
    cfg = decisiones["geomarketing"]["prioridad_despliegue"]
    criterio = cfg["criterio"]
    if criterio not in _CRITERIO_TO_COLUMN:
        raise ValueError(
            f"Criterio desconocido: {criterio!r}. "
            f"Disponibles: {sorted(_CRITERIO_TO_COLUMN)}"
        )
    col, direction = _CRITERIO_TO_COLUMN[criterio]
    ascending = direction == "asc"

    # Si arrancar_por_muni está fijado, lo forzamos a la posición 1.
    arrancar = cfg.get("arrancar_por_muni")

    df = df_viability.copy().sort_values(col, ascending=ascending, kind="stable")
    if arrancar and arrancar in df["municipio"].values:
        first = df[df["municipio"] == arrancar]
        rest = df[df["municipio"] != arrancar]
        df = pd.concat([first, rest], ignore_index=True)

    df = df.reset_index(drop=True)
    df["orden_despliegue"] = df.index + 1
    df["criterio_valor"] = df[col]

    # Mapeo año-objetivo según topes anuales del bloque despliegue
    sedes_max = int(decisiones["despliegue"]["sedes_max_anuales"])
    n = len(df)
    anios = np.minimum(
        np.ceil(np.arange(1, n + 1) / max(sedes_max, 1)).astype(int),
        20,
    )
    df["anio_objetivo_despliegue"] = anios

    cols_out = [
        "orden_despliegue", "codigo", "municipio",
        "criterio_valor", "anio_objetivo_despliegue",
    ]
    return df[cols_out]

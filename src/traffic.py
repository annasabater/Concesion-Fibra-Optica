"""traffic.py — cálculo del tráfico ABAST y mayorista por municipio.

Tráfico ABAST (autoprestación):
    bw_abast_mbps = sedes_abast × bw_por_sede_mbps / overbooking_abast

Tráfico mayorista (pizarra del profesor 07/05/2026):
    hogares_teoricos = hab / habitantes_por_hogar
    cuota_operadores = _cuota_alpha(num_operadores, año, decisiones)
    clientes = hogares_teoricos × cuota_operadores × penetracion_fibra_pct
    bw_mayorista_mbps = clientes × bw_por_hogar_mbps / overbooking

Las dos componentes se desacoplan en el cálculo (lo pide el prompt 03) y se
agregan a posteriori con `aggregate_traffic_by_municipality`.

API pública (ver `src/prompts/03_traffic.md`):
    traffic_abast(df, decisiones) -> DataFrame
    traffic_mayorista(df, decisiones, año) -> DataFrame
    _cuota_alpha(num_operadores, año, decisiones) -> float
    aggregate_traffic_by_municipality(df_abast, df_mayorista) -> DataFrame
    compute_traffic(df, decisiones, año) -> DataFrame   # wrapper end-to-end
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# _cuota_alpha
# ---------------------------------------------------------------------------

def _cuota_alpha(num_operadores: int, año: int, decisiones: dict) -> float:
    """Cuota de mercado mayorista entre operadores ya presentes.

    Tres estrategias en `decisiones['mayorista']['cuota_mercado']['tipo']`:
        - 'equilibrio': α = 1 / (num_operadores + 1)  (entramos como uno más)
        - 'agresivo':   α = 1 / num_operadores         (desplazamos a uno)
        - 'rampa':      α(año) = α_objetivo × min(año / anios_rampa, 1)

    Args:
        num_operadores: operadores presentes en el municipio (1..5).
        año: año de la concesión (1..20). Si año==0, devuelve 0.
        decisiones: configuración del escenario.

    Returns:
        Fracción α ∈ [0, 1].
    """
    if año <= 0:
        return 0.0
    n = max(int(num_operadores), 1)  # defensa: 0 operadores → 1.

    cfg = decisiones["mayorista"]["cuota_mercado"]
    tipo = cfg.get("tipo", "rampa")

    if tipo == "equilibrio":
        alpha = 1.0 / (n + 1)
    elif tipo == "agresivo":
        alpha = 1.0 / n
    elif tipo == "rampa":
        objetivo = float(cfg["alpha_objetivo"])
        anios = max(int(cfg.get("anios_rampa", 1)), 1)
        alpha = objetivo * min(año / anios, 1.0)
    else:
        raise ValueError(
            f"Tipo de cuota desconocido: {tipo!r} "
            "(esperado: equilibrio | agresivo | rampa)"
        )

    return max(0.0, min(alpha, 1.0))


# ---------------------------------------------------------------------------
# traffic_abast
# ---------------------------------------------------------------------------

def traffic_abast(df_topology: pd.DataFrame, decisiones: dict) -> pd.DataFrame:
    """Tráfico ABAST por municipio (determinístico, sin decisiones de mercado).

    Fórmula:
        bw_abast_mbps = sedes_abast × bw_por_sede_mbps / overbooking_abast

    Args:
        df_topology: DataFrame de `load.load_topology`.
        decisiones: configuración del escenario.

    Returns:
        DataFrame con columnas: codigo, municipio, sedes_abast, bw_abast_mbps.
    """
    abast_cfg = decisiones["abast"]
    bw_por_sede = float(abast_cfg["bw_por_sede_mbps"])
    overbooking = float(abast_cfg.get("overbooking", 1)) or 1.0

    out = df_topology[["codigo", "municipio", "sedes_abast"]].copy()
    out["bw_abast_mbps"] = out["sedes_abast"].astype(float) * bw_por_sede / overbooking
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------------
# traffic_mayorista
# ---------------------------------------------------------------------------

def traffic_mayorista(
    df_topology: pd.DataFrame,
    decisiones: dict,
    año: int = 20,
) -> pd.DataFrame:
    """Tráfico mayorista por municipio en el año dado.

    Fórmula desglosada (pizarra del profesor 07/05/2026):
        hogares_teoricos = hab / habitantes_por_hogar
        cuota_operadores = _cuota_alpha(num_operadores, año, decisiones)
        clientes = hogares_teoricos × cuota_operadores × penetracion_fibra_pct
        bw_mbps = clientes × bw_por_hogar_mbps / overbooking

    Args:
        df_topology: DataFrame de `load.load_topology`.
        decisiones: configuración del escenario.
        año: año de la concesión (1..20). Default 20 (régimen estacionario).

    Returns:
        DataFrame con columnas: codigo, municipio, hogares_teoricos,
        cuota_operadores, penetracion_fibra, clientes_mayorista,
        bw_mayorista_mbps.
    """
    cfg = decisiones["mayorista"]
    hab_por_hogar = float(cfg["habitantes_por_hogar"])
    bw_por_hogar = float(cfg["bw_por_hogar_mbps"])
    overbooking = float(cfg.get("overbooking", 1)) or 1.0
    penetracion = float(cfg.get("penetracion_fibra_pct", 1.0))

    out = df_topology[["codigo", "municipio", "hab", "num_operadores"]].copy()
    out["hogares_teoricos"] = out["hab"].astype(float) / hab_por_hogar
    out["cuota_operadores"] = out["num_operadores"].apply(
        lambda n: _cuota_alpha(int(n), año, decisiones)
    )
    out["penetracion_fibra"] = penetracion
    out["clientes_mayorista"] = (
        out["hogares_teoricos"] * out["cuota_operadores"] * out["penetracion_fibra"]
    )
    out["bw_mayorista_mbps"] = (
        out["clientes_mayorista"] * bw_por_hogar / overbooking
    )
    out = out.drop(columns=["hab", "num_operadores"])
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------------
# aggregate_traffic_by_municipality
# ---------------------------------------------------------------------------

def aggregate_traffic_by_municipality(
    df_abast: pd.DataFrame,
    df_mayorista: pd.DataFrame,
) -> pd.DataFrame:
    """Junta ABAST + mayorista por municipio.

    Args:
        df_abast: salida de `traffic_abast`.
        df_mayorista: salida de `traffic_mayorista`.

    Returns:
        DataFrame con columnas: codigo, municipio, bw_abast_mbps,
        bw_mayorista_mbps, bw_total_mbps.
    """
    a = df_abast[["codigo", "municipio", "bw_abast_mbps"]]
    m = df_mayorista[["codigo", "bw_mayorista_mbps"]]
    out = a.merge(m, on="codigo", how="left").fillna({"bw_mayorista_mbps": 0.0})
    out["bw_total_mbps"] = out["bw_abast_mbps"] + out["bw_mayorista_mbps"]
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------------
# compute_traffic — wrapper end-to-end usado por main.py
# ---------------------------------------------------------------------------

def compute_traffic(
    df: pd.DataFrame,
    decisiones: dict,
    año: int = 20,
) -> pd.DataFrame:
    """Wrapper que ejecuta ABAST + mayorista + agregación en un único paso.

    Args:
        df: DataFrame de topología.
        decisiones: configuración del escenario.
        año: año de la concesión (default 20, régimen estacionario).

    Returns:
        DataFrame agregado (codigo, municipio, bw_abast_mbps,
        bw_mayorista_mbps, bw_total_mbps).
    """
    df_abast = traffic_abast(df, decisiones)
    df_mayo = traffic_mayorista(df, decisiones, año=año)
    df_total = aggregate_traffic_by_municipality(df_abast, df_mayo)
    logger.info(
        "compute_traffic[año=%d]: ABAST=%.1f Gbps, mayorista=%.1f Gbps, total=%.1f Gbps",
        año,
        df_total["bw_abast_mbps"].sum() / 1000,
        df_total["bw_mayorista_mbps"].sum() / 1000,
        df_total["bw_total_mbps"].sum() / 1000,
    )
    return df_total

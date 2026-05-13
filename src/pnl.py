"""pnl.py — cuenta de resultados a 20 años + KPIs financieros.

Combina ingresos, OPEX y CAPEX para producir EBITDA, EBIT, resultado
neto y los KPIs (NPV, IRR, payback) usando la tasa de descuento de
`decisiones.descuento.tasa`.

Función pública:
    compute_pnl(capex_df, opex_df, revenue_df, decisiones) -> pd.DataFrame
"""

from __future__ import annotations

import logging

import numpy_financial as npf
import pandas as pd

logger = logging.getLogger(__name__)

_N_ANIOS = 20
_VIDA_UTIL_PONDERADA = 15  # años (promedio ponderado de equipos y obra civil)


def compute_pnl(
    capex_df: pd.DataFrame | None,
    opex_df: pd.DataFrame | None,
    revenue_df: pd.DataFrame | None,
    decisiones: dict,
) -> pd.DataFrame:
    """Construye la cuenta de resultados anual + KPIs a 20 años.

    Columnas de salida:
        anio, ingresos_eur, opex_eur, ebitda_eur, capex_eur,
        amortizacion_eur, ebit_eur, resultado_neto_eur,
        fcl_eur, fcl_acumulado_eur

    KPIs en df.attrs:
        npv (float), irr (float), payback_anios (int),
        ebitda_margin_y20 (float)

    Args:
        capex_df: salida de `capex.compute_capex`.
        opex_df: salida de `opex.compute_opex`.
        revenue_df: salida de `revenue.compute_revenue`.
        decisiones: configuración del escenario (tasa de descuento, impuesto).

    Returns:
        DataFrame de 20 filas con KPIs en attrs.
    """
    _empty_cols = [
        "anio", "ingresos_eur", "opex_eur", "ebitda_eur", "capex_eur",
        "amortizacion_eur", "ebit_eur", "resultado_neto_eur",
        "fcl_eur", "fcl_acumulado_eur",
    ]

    if capex_df is None or opex_df is None or revenue_df is None:
        logger.warning("compute_pnl: faltan inputs; retornando DataFrame vacío.")
        return pd.DataFrame(columns=_empty_cols)

    # ---- parámetros financieros ----
    tasa = float(decisiones["descuento"]["tasa"])
    impuesto = float(decisiones.get("impuestos", {}).get("sociedades_pct", 0.25))

    # ---- índices por año ----
    capex_idx = capex_df.set_index("anio")
    opex_idx = opex_df.set_index("anio")
    rev_idx = revenue_df.set_index("anio")

    rows = []
    capex_acum = 0.0
    fcl_acum = 0.0

    for anio in range(1, _N_ANIOS + 1):
        ingresos = float(rev_idx.loc[anio, "total_eur"]) if anio in rev_idx.index else 0.0
        opex_total = float(opex_idx.loc[anio, "total_eur"]) if anio in opex_idx.index else 0.0
        capex_anio = float(capex_idx.loc[anio, "total_eur"]) if anio in capex_idx.index else 0.0

        capex_acum += capex_anio

        # EBITDA = ingresos - OPEX total
        ebitda = ingresos - opex_total

        # Amortización lineal: CAPEX acumulado / vida útil ponderada
        amortizacion = capex_acum / _VIDA_UTIL_PONDERADA

        # EBIT = EBITDA - amortización
        ebit = ebitda - amortizacion

        # Resultado neto = EBIT × (1 - impuesto); si EBIT < 0, no hay impuesto
        if ebit > 0:
            resultado_neto = ebit * (1 - impuesto)
        else:
            resultado_neto = ebit  # pérdidas no generan impuesto

        # FCL (free cash flow) = EBITDA - CAPEX del año
        # (EBITDA es proxy de flujo operativo; CAPEX es inversión)
        fcl = ebitda - capex_anio
        fcl_acum += fcl

        rows.append({
            "anio": anio,
            "ingresos_eur": round(ingresos),
            "opex_eur": round(opex_total),
            "ebitda_eur": round(ebitda),
            "capex_eur": round(capex_anio),
            "amortizacion_eur": round(amortizacion),
            "ebit_eur": round(ebit),
            "resultado_neto_eur": round(resultado_neto),
            "fcl_eur": round(fcl),
            "fcl_acumulado_eur": round(fcl_acum),
        })

    pnl_df = pd.DataFrame(rows)

    # ---- KPIs ----
    fcl_series = pnl_df["fcl_eur"].tolist()

    try:
        npv = float(npf.npv(tasa, fcl_series))
    except Exception as e:
        logger.warning("NPV no calculable: %s", e)
        npv = float("nan")

    try:
        irr = float(npf.irr(fcl_series))
    except Exception as e:
        logger.warning("IRR no calculable: %s", e)
        irr = float("nan")

    # Payback: primer año donde FCL acumulado > 0
    payback = _N_ANIOS  # default: no recuperado en 20 años
    for _, row in pnl_df.iterrows():
        if row["fcl_acumulado_eur"] > 0:
            payback = int(row["anio"])
            break

    # EBITDA margin año 20
    last = pnl_df.iloc[-1]
    ebitda_margin_y20 = (
        float(last["ebitda_eur"]) / float(last["ingresos_eur"])
        if float(last["ingresos_eur"]) > 0 else 0.0
    )

    pnl_df.attrs = {
        "npv": round(npv),
        "irr": irr,
        "payback_anios": payback,
        "ebitda_margin_y20": round(ebitda_margin_y20, 4),
    }

    logger.info(
        "compute_pnl: NPV=%.2f M€ | IRR=%.1f%% | Payback=%d años | "
        "EBITDA margin año20=%.1f%%",
        npv / 1e6,
        irr * 100 if not pd.isna(irr) else float("nan"),
        payback,
        ebitda_margin_y20 * 100,
    )
    return pnl_df

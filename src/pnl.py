"""pnl.py — cuenta de resultados a 20 años + KPIs financieros.

Combina ingresos, OPEX y CAPEX para producir EBITDA, EBIT, resultado
neto y los KPIs (NPV, IRR, payback) usando la tasa de descuento de
`decisiones.descuento.tasa`.

Implementación pendiente — ver `src/prompts/08_pnl.md`.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def compute_pnl(
    capex: pd.DataFrame,
    opex: pd.DataFrame,
    revenue: pd.DataFrame,
    decisiones: dict,
) -> pd.DataFrame:
    """Construye la cuenta de resultados anual + KPIs a 20 años.

    Args:
        capex: DataFrame de `capex.compute_capex`.
        opex: DataFrame de `opex.compute_opex`.
        revenue: DataFrame de `revenue.compute_revenue`.
        decisiones: configuración del escenario (tasa de descuento, años).

    Returns:
        DataFrame con columnas (anio, ingresos, opex, ebitda, capex, ebit,
        resultado_neto, flujo_caja, flujo_caja_acumulado) y atributos
        agregados (NPV, IRR, payback) en `df.attrs`.

    Raises:
        NotImplementedError: hasta que se implemente el prompt 08.
    """
    raise NotImplementedError("Pendiente — ver src/prompts/08_pnl.md")

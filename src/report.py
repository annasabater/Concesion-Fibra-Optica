"""report.py — generación del Excel de salida y los PDF de oferta.

Produce el Excel consolidado del escenario (CAPEX/OPEX/ingresos/P&L,
una hoja por bloque) y los PDF para entrega: oferta técnica,
oferta económica y resumen ejecutivo.

Implementación pendiente — ver `src/prompts/10_report.md`.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def generate_reports(
    pnl: pd.DataFrame,
    capex: pd.DataFrame,
    opex: pd.DataFrame,
    revenue: pd.DataFrame,
    output_dir: Path,
    decisiones: dict,
) -> list[Path]:
    """Genera el Excel y los PDF de la oferta para el escenario.

    Args:
        pnl: DataFrame de `pnl.compute_pnl`.
        capex: DataFrame de `capex.compute_capex`.
        opex: DataFrame de `opex.compute_opex`.
        revenue: DataFrame de `revenue.compute_revenue`.
        output_dir: carpeta donde escribir los archivos.
        decisiones: configuración del escenario (para incluir en el PDF).

    Returns:
        Lista de paths a los archivos generados.

    Raises:
        NotImplementedError: hasta que se implemente el prompt 10.
    """
    raise NotImplementedError("Pendiente — ver src/prompts/10_report.md")

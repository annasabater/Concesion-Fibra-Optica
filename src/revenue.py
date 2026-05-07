"""revenue.py — ingresos plurianuales (ABAST + mayorista).

ABAST: 1.000 €/mes por sede conectada (alta gratis). Mayorista: 1.500 €
de alta + 700 €/mes por sede mayorista. Conexión gradual según el plan
de despliegue (`decisiones.despliegue`) y la rampa de cuota α(t).

Implementación pendiente — ver `src/prompts/07_revenue.md`.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def compute_revenue(
    df: pd.DataFrame,
    decisiones: dict,
    parametros: dict,
) -> pd.DataFrame:
    """Calcula los ingresos plurianuales por escenario.

    Args:
        df: DataFrame de topología.
        decisiones: configuración del escenario.
        parametros: tarifas (alta/recurrente ABAST y mayorista).

    Returns:
        DataFrame con columnas (anio, ingresos_abast, ingresos_mayorista_alta,
        ingresos_mayorista_recurrente, total).

    Raises:
        NotImplementedError: hasta que se implemente el prompt 07.
    """
    raise NotImplementedError("Pendiente — ver src/prompts/07_revenue.md")

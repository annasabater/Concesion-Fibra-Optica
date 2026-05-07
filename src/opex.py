"""opex.py — costes operativos plurianuales.

Suma mantenimiento de fibra (250 €/km·año × km activos), mantenimiento de
equipos (10% del CAPEX activo), mantenimiento SI, derechos de paso e
impuestos (3% ingresos), costes de venta mayorista (10% de ingresos
mayorista) y gastos generales (700.000 €/año), modulado por la red
realmente activa cada año según el plan de despliegue.

Implementación pendiente — ver `src/prompts/06_opex.md`.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def compute_opex(
    capex: pd.DataFrame,
    df: pd.DataFrame,
    decisiones: dict,
    parametros: dict,
) -> pd.DataFrame:
    """Calcula el OPEX plurianual.

    Args:
        capex: DataFrame de `capex.compute_capex`.
        df: DataFrame de topología (para km activos).
        decisiones: configuración del escenario.
        parametros: tarifas y costes unitarios.

    Returns:
        DataFrame con columnas (anio, mant_fibra, mant_equipos, mant_si,
        derechos_paso, costes_ventas, gastos_generales, total).

    Raises:
        NotImplementedError: hasta que se implemente el prompt 06.
    """
    raise NotImplementedError("Pendiente — ver src/prompts/06_opex.md")

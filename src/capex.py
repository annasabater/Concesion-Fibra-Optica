"""capex.py — inversiones (CAPEX) por año y por anillo.

Combina obra civil (€/m), altas de sede (ABAST y mayorista), chasis de
nodos, equipos seleccionados por `equipment.py`, y el CAPEX extra del
datacenter A900. Agrega los totales por año y por anillo siguiendo el
plan de despliegue (`decisiones.despliegue`).

Implementación pendiente — ver `src/prompts/05_capex.md`.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def compute_capex(
    df: pd.DataFrame,
    equipment: pd.DataFrame,
    decisiones: dict,
    parametros: dict,
) -> pd.DataFrame:
    """Calcula el CAPEX por año y por anillo.

    Args:
        df: DataFrame de topología.
        equipment: DataFrame de `equipment.assign_equipment`.
        decisiones: configuración del escenario.
        parametros: tarifas y costes unitarios cargados de la hoja Parámetros.

    Returns:
        DataFrame con columnas (anio, anillo, obra_civil_eur, altas_eur,
        equipos_eur, datacenter_eur, total_eur).

    Raises:
        NotImplementedError: hasta que se implemente el prompt 05.
    """
    raise NotImplementedError("Pendiente — ver src/prompts/05_capex.md")

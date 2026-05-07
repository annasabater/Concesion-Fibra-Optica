"""traffic.py — cálculo del tráfico ABAST y mayorista por municipio y año.

Tráfico ABAST: sedes_abast × bw_por_sede × overbooking_abast.
Tráfico mayorista: (hab/habitantes_por_hogar) × α(t) × bw_por_hogar /
overbooking, donde α(t) sigue la estrategia de cuota (equilibrio, agresivo
o rampa) declarada en `decisiones.yaml`.

Implementación pendiente — ver `src/prompts/03_traffic.md`.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def compute_traffic(df: pd.DataFrame, decisiones: dict) -> pd.DataFrame:
    """Calcula el tráfico ABAST + mayorista por municipio y por año.

    Args:
        df: DataFrame de topología con `sedes_abast`, `hab`, `num_operadores`.
        decisiones: configuración del escenario (ver `load.load_decisiones`).

    Returns:
        DataFrame con columnas (codigo, anio, traffic_abast_mbps,
        traffic_mayorista_mbps, traffic_total_mbps).

    Raises:
        NotImplementedError: hasta que se implemente el prompt 03.
    """
    raise NotImplementedError("Pendiente — ver src/prompts/03_traffic.md")

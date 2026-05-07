"""equipment.py — tráfico acumulado y selección de equipo por nodo.

Recorre el grafo desde las hojas hacia A900 sumando tráfico, y aplica los
umbrales de `decisiones.yaml` (umbral_10p_a_20p, …, umbral_40p_a_mpls)
para elegir entre equipo Ethernet de 10/20/40 puertos, MPLS troncal u
óptico de 40 lambdas.

Implementación pendiente — ver `src/prompts/04_equipment.md`.
"""

from __future__ import annotations

import logging

import networkx as nx
import pandas as pd

logger = logging.getLogger(__name__)


def assign_equipment(
    graph: nx.DiGraph,
    traffic: pd.DataFrame,
    decisiones: dict,
) -> pd.DataFrame:
    """Asigna tráfico acumulado y tipo de equipo a cada nodo del grafo.

    Args:
        graph: grafo de `topology.build_topology`.
        traffic: DataFrame de `traffic.compute_traffic`.
        decisiones: configuración del escenario.

    Returns:
        DataFrame por nodo con (codigo, anio, traffic_acumulado_mbps,
        equipo_tipo, equipo_capex_eur).

    Raises:
        NotImplementedError: hasta que se implemente el prompt 04.
    """
    raise NotImplementedError("Pendiente — ver src/prompts/04_equipment.md")

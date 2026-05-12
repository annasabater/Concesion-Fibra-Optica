"""Tests para src/equipment.py — happy path según el spec del prompt 04."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pandas as pd
import pytest

from src.equipment import (
    assign_equipment,
    cumulative_traffic,
    select_equipment,
    total_capex_equipos,
)
from src.load import load_decisiones, load_parameters, load_topology
from src.topology import build_graph
from src.traffic import compute_traffic

DATA_DIR = Path(__file__).parent.parent / "data"
TOPOLOGY_FILE = DATA_DIR / "Despliegue de REd Municipios 2026.xlsx"
PARAMETERS_FILE = DATA_DIR / "Despliegue de REd Municipios 2026.xlsx"
DECISIONES_FILE = DATA_DIR / "decisiones.yaml"


@pytest.fixture(scope="module")
def df_topology():
    return load_topology(TOPOLOGY_FILE)


@pytest.fixture(scope="module")
def graph(df_topology):
    return build_graph(df_topology)


@pytest.fixture(scope="module")
def parametros():
    return load_parameters(PARAMETERS_FILE)


@pytest.fixture(scope="module")
def decisiones_base():
    return load_decisiones(DECISIONES_FILE, "base")


@pytest.fixture(scope="module")
def traffic_df(df_topology, decisiones_base):
    return compute_traffic(df_topology, decisiones_base, año=20)


# ---------------------------------------------------------------------------
# cumulative_traffic
# ---------------------------------------------------------------------------

class TestCumulativeTraffic:

    def test_linear_chain_5_nodes(self):
        # Chain A→B→C→D→E (hijo→padre apuntando a E como root) con
        # tráfico propio [10, 20, 30, 40, 50] en [A, B, C, D, E].
        # Acumulado esperado: A=10, B=30, C=60, D=100, E=150.
        g = nx.DiGraph()
        for code, n in enumerate(["A", "B", "C", "D", "E"], start=1):
            g.add_node(
                n, codigo=code, tier="acceso",
                anillos_agregacion=set(), anillos_troncal=set(),
                hab=0, sedes_abast=0, num_operadores=1, km=0.0,
            )
        for u, v in [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E")]:
            g.add_edge(u, v, tipo="acceso", km=1.0)

        traffic = pd.DataFrame({
            "codigo": [1, 2, 3, 4, 5],
            "municipio": ["A", "B", "C", "D", "E"],
            "bw_total_mbps": [10.0, 20.0, 30.0, 40.0, 50.0],
        })

        df = cumulative_traffic(g, traffic)
        bw = df.set_index("municipio")["bw_acumulado_mbps"].to_dict()
        assert bw["A"] == pytest.approx(10.0)
        assert bw["B"] == pytest.approx(30.0)
        assert bw["C"] == pytest.approx(60.0)
        assert bw["D"] == pytest.approx(100.0)
        assert bw["E"] == pytest.approx(150.0)

    def test_a900_equals_total_territory(self, graph, traffic_df):
        df = cumulative_traffic(graph, traffic_df)
        bw_a900 = float(df.loc[df["municipio"] == "A900", "bw_acumulado_mbps"].iloc[0])
        bw_total = float(traffic_df["bw_total_mbps"].sum())
        assert bw_a900 == pytest.approx(bw_total, rel=1e-3)

    def test_900_rows(self, graph, traffic_df):
        df = cumulative_traffic(graph, traffic_df)
        assert len(df) == 900


# ---------------------------------------------------------------------------
# select_equipment
# ---------------------------------------------------------------------------

class TestSelectEquipment:

    def test_900_rows(self, graph, traffic_df, decisiones_base, parametros):
        df_cum = cumulative_traffic(graph, traffic_df)
        df = select_equipment(df_cum, decisiones_base, parametros)
        assert len(df) == 900

    def test_high_link_count_scales_to_mpls(
        self, graph, traffic_df, decisiones_base, parametros,
    ):
        # Crear un nodo agg artificial con 50 downstream → debe escalar a MPLS.
        df_cum = cumulative_traffic(graph, traffic_df)
        # Buscar un nodo agg para mutar (o construir uno sintético en df).
        sample = df_cum[df_cum["tier"] == "agregacion"].head(1).copy()
        sample["n_downstream_links"] = 50
        sample["bw_acumulado_mbps"] = 50_000  # 50 Gbps
        df = select_equipment(sample, decisiones_base, parametros)
        equipo = df.iloc[0]["equipo_principal"]
        assert "mpls" in equipo

    def test_a900_has_mpls_optical_and_dc_extra(
        self, graph, traffic_df, decisiones_base, parametros,
    ):
        df_cum = cumulative_traffic(graph, traffic_df)
        df = select_equipment(df_cum, decisiones_base, parametros)
        a900 = df[df["municipio"] == "A900"].iloc[0]
        assert "mpls" in a900["equipo_principal"]
        # capex_extra debe traer el datacenter_a900.capex_extra del YAML (5M€).
        assert a900["capex_extra"] == pytest.approx(5_000_000)


# ---------------------------------------------------------------------------
# assign_equipment + total_capex_equipos (wrapper end-to-end)
# ---------------------------------------------------------------------------

class TestAssignEquipment:

    def test_pipeline_e2e(self, graph, traffic_df, decisiones_base, parametros):
        df = assign_equipment(graph, traffic_df, decisiones_base, parametros)
        assert len(df) == 900
        # Sanity: CAPEX total > 0
        totals = total_capex_equipos(df)
        assert totals["total"] > 0

    def test_capex_in_expected_magnitude(
        self, graph, traffic_df, decisiones_base, parametros,
    ):
        df = assign_equipment(graph, traffic_df, decisiones_base, parametros)
        totals = total_capex_equipos(df)
        # Decenas a centenas de millones según el prompt.
        assert 10_000_000 <= totals["total"] <= 1_000_000_000

    def test_all_5000_sedes_have_client_equipment(
        self, graph, traffic_df, decisiones_base, parametros,
    ):
        df = assign_equipment(graph, traffic_df, decisiones_base, parametros)
        # Suma de sedes_abast = 5000 → suma de equipo_cliente_capex = 5000 × 300
        assert df["sedes_abast"].sum() == 5000
        assert df["equipo_cliente_capex"].sum() == pytest.approx(5000 * 300)

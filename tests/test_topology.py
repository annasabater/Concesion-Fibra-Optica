"""Tests para src/topology.py — construcción del grafo y stats por anillo."""
from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from src.load import load_topology
from src.topology import (
    ROOT_NODE,
    build_graph,
    get_downstream_nodes,
    get_root,
    resolve_aggregation_ring,
    stats_by_ring,
    draw_rings_only,
    draw_full_topology,
)


DATA_DIR = Path(__file__).parent.parent / "data"
EXCEL_PATH = DATA_DIR / "Despliegue de REd Municipios 2026.xlsx"


@pytest.fixture(scope="module")
def df():
    if not EXCEL_PATH.exists():
        pytest.skip(f"No existe {EXCEL_PATH}")
    return load_topology(EXCEL_PATH)


@pytest.fixture(scope="module")
def graph(df):
    return build_graph(df)


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------

class TestBuildGraph:

    def test_es_digrafo(self, graph):
        assert isinstance(graph, nx.DiGraph)

    def test_900_nodos(self, graph):
        assert graph.number_of_nodes() == 900

    def test_al_menos_900_aristas(self, graph):
        # 799 acceso + ~91 anillo agg + ~12 anillo troncal cíclicas ≥ 900.
        assert graph.number_of_edges() >= 900

    def test_a900_existe(self, graph):
        assert ROOT_NODE in graph

    def test_a900_atributos_correctos(self, graph):
        a900 = graph.nodes[ROOT_NODE]
        assert a900["tier"] == "troncal"
        assert "T1" in a900["anillos_troncal"]
        assert "T2" in a900["anillos_troncal"]
        assert "T3" in a900["anillos_troncal"]
        assert "A1" in a900["anillos_agregacion"]
        assert "A2" in a900["anillos_agregacion"]

    def test_a1_es_acceso(self, graph):
        assert graph.nodes["A1"]["tier"] == "acceso"

    def test_aristas_acceso_apuntan_hacia_padre(self, graph):
        # A1 → A300 según CLAUDE.md (cadena A1→A300→A630→...→A800).
        succs = [
            v for u, v, d in graph.out_edges("A1", data=True)
            if d.get("tipo") == "acceso"
        ]
        assert len(succs) == 1
        assert succs[0] == "A300"


# ---------------------------------------------------------------------------
# Helpers de navegación
# ---------------------------------------------------------------------------

class TestNavigation:

    def test_get_root_devuelve_a900(self, graph):
        assert get_root(graph) == "A900"

    def test_resolve_aggregation_ring_a1_incluye_a2(self, graph):
        # Cadena A1 → A300 → A630 → A752 → A774 → A800 (en A2).
        rings = resolve_aggregation_ring(graph, "A1")
        assert "A2" in rings

    def test_resolve_aggregation_ring_para_nodo_agg(self, graph):
        # Un nodo de agregación devuelve directamente sus anillos.
        rings = resolve_aggregation_ring(graph, "A800")
        assert rings == {"A2"}

    def test_resolve_aggregation_ring_a900(self, graph):
        rings = resolve_aggregation_ring(graph, ROOT_NODE)
        assert rings == {"A1", "A2"}

    def test_get_downstream_nodes_a800_no_vacio(self, graph):
        # A800 es nodo de agg en A2; tiene muchos accesos colgando.
        downstream = get_downstream_nodes(graph, "A800")
        assert len(downstream) > 0

    def test_get_downstream_nodes_a1_es_hoja(self, graph):
        # A1 es nodo de acceso terminal — no tiene nadie aguas abajo.
        assert get_downstream_nodes(graph, "A1") == set()


# ---------------------------------------------------------------------------
# stats_by_ring
# ---------------------------------------------------------------------------

class TestStatsByRing:

    def test_14_filas(self, graph):
        df = stats_by_ring(graph)
        assert len(df) == 14

    def test_distribucion_3_troncal_11_agregacion(self, graph):
        df = stats_by_ring(graph)
        counts = df["tipo"].value_counts().to_dict()
        assert counts["agregacion"] == 11
        assert counts["troncal"] == 3

    def test_columnas_esperadas(self, graph):
        df = stats_by_ring(graph)
        expected = {
            "anillo", "tipo", "n_nodos", "n_munis_cubiertos",
            "n_sedes_abast", "total_hab", "km_existing", "km_acceso_construido",
        }
        assert set(df.columns) == expected

    def test_a2_concentra_la_mayoria_del_acceso(self, graph):
        df = stats_by_ring(graph)
        a2 = df[df["anillo"] == "A2"].iloc[0]
        # Per CLAUDE.md gotcha: ~793 munis resuelven a A2.
        assert a2["n_munis_cubiertos"] > 700

    def test_anillos_y_tipos_son_los_esperados(self, graph):
        df = stats_by_ring(graph)
        assert set(df["anillo"]) == {f"A{i}" for i in range(1, 12)} | {"T1", "T2", "T3"}


# ---------------------------------------------------------------------------
# Visualización (smoke tests — sólo verifican que no peta y crea el archivo)
# ---------------------------------------------------------------------------

class TestVisualization:

    def test_draw_rings_only_genera_png(self, graph, tmp_path):
        output = tmp_path / "rings.png"
        draw_rings_only(graph, output)
        assert output.exists()
        assert output.stat().st_size > 0

    def test_draw_full_topology_genera_png(self, graph, tmp_path):
        output = tmp_path / "full.png"
        draw_full_topology(graph, output)
        assert output.exists()
        assert output.stat().st_size > 0

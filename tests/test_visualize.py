"""Smoke tests para src/visualize.py — la batería topológica del prompt 09."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.load import load_topology
from src.topology import build_graph
from src.visualize import (
    draw_ring_detail,
    draw_rings_only,
    generate_diagrams,
)


DATA_DIR = Path(__file__).parent.parent / "data"
EXCEL_PATH = DATA_DIR / "Despliegue de REd Municipios 2026.xlsx"


@pytest.fixture(scope="module")
def graph():
    if not EXCEL_PATH.exists():
        pytest.skip(f"No existe {EXCEL_PATH}")
    return build_graph(load_topology(EXCEL_PATH))


def test_draw_rings_only_genera_png_y_svg(graph, tmp_path):
    base = tmp_path / "anillos"
    png, svg = draw_rings_only(graph, base)
    assert png.exists() and png.stat().st_size > 0
    assert svg.exists() and svg.stat().st_size > 0
    assert png.suffix == ".png"
    assert svg.suffix == ".svg"


def test_draw_ring_detail_a2(graph, tmp_path):
    base = tmp_path / "detalle_A2"
    png, svg = draw_ring_detail(graph, "A2", base)
    assert png.exists() and svg.exists()


def test_draw_ring_detail_a11(graph, tmp_path):
    base = tmp_path / "detalle_A11"
    png, svg = draw_ring_detail(graph, "A11", base)
    assert png.exists() and svg.exists()


def test_draw_ring_detail_invalido_lanza(graph, tmp_path):
    with pytest.raises(ValueError):
        draw_ring_detail(graph, "A99", tmp_path / "x")


def test_generate_diagrams_produce_4_figuras(graph, tmp_path):
    import pandas as pd
    paths = generate_diagrams(graph, pd.DataFrame(), tmp_path)
    # 4 figuras × 2 formatos = 8 archivos.
    assert len(paths) == 8
    for p in paths:
        assert p.exists()
        assert p.stat().st_size > 0
    # Verificar que se han creado las 4 figuras esperadas.
    names = {p.stem for p in paths}
    assert names == {
        "topologia_anillos",
        "topologia_detalle_A2",
        "topologia_detalle_A6",
        "topologia_detalle_A11",
    }

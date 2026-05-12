"""Tests para src/traffic.py — happy path según el spec del prompt 03."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.load import load_decisiones, load_topology
from src.traffic import (
    _cuota_alpha,
    aggregate_traffic_by_municipality,
    compute_traffic,
    traffic_abast,
    traffic_mayorista,
)

DATA_DIR = Path(__file__).parent.parent / "data"
TOPOLOGY_FILE = DATA_DIR / "Despliegue de REd Municipios 2026.xlsx"
DECISIONES_FILE = DATA_DIR / "decisiones.yaml"


@pytest.fixture(scope="module")
def df_topology():
    return load_topology(TOPOLOGY_FILE)


@pytest.fixture(scope="module")
def decisiones_base():
    return load_decisiones(DECISIONES_FILE, "base")


# ---------------------------------------------------------------------------
# _cuota_alpha
# ---------------------------------------------------------------------------

class TestCuotaAlpha:

    def test_year_zero_returns_zero(self, decisiones_base):
        assert _cuota_alpha(num_operadores=2, año=0, decisiones=decisiones_base) == 0.0

    def test_rampa_at_full_year_equals_objetivo(self, decisiones_base):
        # base: alpha_objetivo=0.40, anios_rampa=8, tipo='rampa'
        alpha = _cuota_alpha(num_operadores=2, año=8, decisiones=decisiones_base)
        assert alpha == pytest.approx(0.40, rel=1e-9)

    def test_rampa_half_way(self, decisiones_base):
        # rampa de 8 años en año 4 → 0.40 × 0.5 = 0.20
        alpha = _cuota_alpha(num_operadores=2, año=4, decisiones=decisiones_base)
        assert alpha == pytest.approx(0.20, rel=1e-9)

    def test_rampa_after_horizon_caps_at_objetivo(self, decisiones_base):
        # año 20 con rampa de 8 → α capeado al objetivo
        alpha = _cuota_alpha(num_operadores=3, año=20, decisiones=decisiones_base)
        assert alpha == pytest.approx(0.40, rel=1e-9)

    def test_equilibrio_strategy(self, decisiones_base):
        cfg = dict(decisiones_base)
        cfg["mayorista"] = dict(cfg["mayorista"])
        cfg["mayorista"]["cuota_mercado"] = {"tipo": "equilibrio"}
        # 2 operadores presentes → entramos como uno más → 1/(2+1) = 0.333…
        alpha = _cuota_alpha(num_operadores=2, año=1, decisiones=cfg)
        assert alpha == pytest.approx(1.0 / 3.0, rel=1e-9)

    def test_agresivo_strategy(self, decisiones_base):
        cfg = dict(decisiones_base)
        cfg["mayorista"] = dict(cfg["mayorista"])
        cfg["mayorista"]["cuota_mercado"] = {"tipo": "agresivo"}
        # 2 operadores → desplazamos a uno → 1/2 = 0.5
        alpha = _cuota_alpha(num_operadores=2, año=1, decisiones=cfg)
        assert alpha == pytest.approx(0.5, rel=1e-9)

    def test_zero_operators_treated_as_one(self, decisiones_base):
        # Defensa: si num_operadores=0 (no debería pasar) tratamos como 1.
        cfg = dict(decisiones_base)
        cfg["mayorista"] = dict(cfg["mayorista"])
        cfg["mayorista"]["cuota_mercado"] = {"tipo": "equilibrio"}
        alpha = _cuota_alpha(num_operadores=0, año=1, decisiones=cfg)
        assert alpha == pytest.approx(0.5, rel=1e-9)


# ---------------------------------------------------------------------------
# traffic_abast
# ---------------------------------------------------------------------------

class TestTrafficAbast:

    def test_a900_traffic(self, df_topology, decisiones_base):
        # A900 tiene 769 sedes ABAST × 100 Mbps × 1/1 = 76.900 Mbps
        df = traffic_abast(df_topology, decisiones_base)
        bw_a900 = float(df.loc[df["municipio"] == "A900", "bw_abast_mbps"].iloc[0])
        assert bw_a900 == pytest.approx(76_900, rel=1e-6)

    def test_total_abast_traffic(self, df_topology, decisiones_base):
        # 5000 sedes × 100 Mbps × 1/1 = 500.000 Mbps total
        df = traffic_abast(df_topology, decisiones_base)
        assert df["bw_abast_mbps"].sum() == pytest.approx(500_000, rel=1e-6)

    def test_900_rows(self, df_topology, decisiones_base):
        df = traffic_abast(df_topology, decisiones_base)
        assert len(df) == 900


# ---------------------------------------------------------------------------
# traffic_mayorista
# ---------------------------------------------------------------------------

class TestTrafficMayorista:

    def test_900_rows_at_year_20(self, df_topology, decisiones_base):
        df = traffic_mayorista(df_topology, decisiones_base, año=20)
        assert len(df) == 900

    def test_year_zero_no_mayorista(self, df_topology, decisiones_base):
        # Año 0 → α=0 → tráfico mayorista = 0 en todos los munis
        df = traffic_mayorista(df_topology, decisiones_base, año=0)
        assert df["bw_mayorista_mbps"].sum() == pytest.approx(0.0, abs=1e-9)

    def test_penetracion_factor_applied(self, df_topology, decisiones_base):
        # Comparar con penetracion=1.0 vs base (0.70): el ratio debe ser 0.70
        cfg_full = dict(decisiones_base)
        cfg_full["mayorista"] = dict(cfg_full["mayorista"])
        cfg_full["mayorista"]["penetracion_fibra_pct"] = 1.0

        df_70 = traffic_mayorista(df_topology, decisiones_base, año=20)
        df_100 = traffic_mayorista(df_topology, cfg_full, año=20)
        ratio = df_70["bw_mayorista_mbps"].sum() / df_100["bw_mayorista_mbps"].sum()
        assert ratio == pytest.approx(0.70, rel=1e-6)

    def test_columns_present(self, df_topology, decisiones_base):
        df = traffic_mayorista(df_topology, decisiones_base, año=20)
        for col in (
            "codigo", "municipio", "hogares_teoricos", "cuota_operadores",
            "penetracion_fibra", "clientes_mayorista", "bw_mayorista_mbps",
        ):
            assert col in df.columns


# ---------------------------------------------------------------------------
# aggregate_traffic_by_municipality + compute_traffic
# ---------------------------------------------------------------------------

class TestAggregate:

    def test_total_equals_sum_of_parts(self, df_topology, decisiones_base):
        df = compute_traffic(df_topology, decisiones_base, año=20)
        assert df["bw_total_mbps"].sum() == pytest.approx(
            df["bw_abast_mbps"].sum() + df["bw_mayorista_mbps"].sum(),
            rel=1e-6,
        )

    def test_compute_traffic_integration(self, df_topology, decisiones_base):
        df = compute_traffic(df_topology, decisiones_base, año=20)
        # ABAST debe ser ~500 Gbps; mayorista varía pero > 0 al año 20.
        assert df["bw_abast_mbps"].sum() == pytest.approx(500_000, rel=1e-6)
        assert df["bw_mayorista_mbps"].sum() > 0

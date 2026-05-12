"""Tests para src/geomarketing.py — happy path según el spec del prompt 03b."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.geomarketing import (
    deployment_priority_order,
    infraestructura_acceso_por_municipio,
    municipal_viability,
    pyme_estimation_per_municipality,
)
from src.load import load_decisiones, load_parameters, load_topology
from src.traffic import traffic_abast, traffic_mayorista

DATA_DIR = Path(__file__).parent.parent / "data"
TOPOLOGY_FILE = DATA_DIR / "Despliegue de REd Municipios 2026.xlsx"
PARAMETERS_FILE = DATA_DIR / "Despliegue de REd Municipios 2026.xlsx"
DECISIONES_FILE = DATA_DIR / "decisiones.yaml"


@pytest.fixture(scope="module")
def df_topology():
    return load_topology(TOPOLOGY_FILE)


@pytest.fixture(scope="module")
def parametros():
    return load_parameters(PARAMETERS_FILE)


@pytest.fixture(scope="module")
def decisiones_base():
    return load_decisiones(DECISIONES_FILE, "base")


# ---------------------------------------------------------------------------
# pyme_estimation_per_municipality
# ---------------------------------------------------------------------------

class TestPymeEstimation:

    def test_900_rows(self, df_topology, decisiones_base):
        df = pyme_estimation_per_municipality(df_topology, decisiones_base)
        assert len(df) == 900

    def test_ratio_50_hab_per_pyme(self, df_topology, decisiones_base):
        # base: habitantes_por_pyme=50. Un muni con N hab → N/50 PYMEs.
        df = pyme_estimation_per_municipality(df_topology, decisiones_base)
        merged = df.merge(
            df_topology[["codigo", "hab"]], on="codigo", how="left"
        )
        # Verificar la fórmula muestra a muestra
        ratio = (merged["n_pymes_estimadas"] / merged["hab"].clip(lower=1))
        # Con habitantes_por_pyme=50 → n_pymes = hab/50 → ratio = 1/50 = 0.02
        # Para munis con hab > 0
        assert ratio[merged["hab"] > 0].round(6).eq(0.02).all()


# ---------------------------------------------------------------------------
# infraestructura_acceso_por_municipio
# ---------------------------------------------------------------------------

class TestInfraestructuraAcceso:

    def test_armario_calle_default(self, df_topology, decisiones_base):
        # base: tipo='armario_calle' → todos los munis acceso usan armario.
        df = infraestructura_acceso_por_municipio(df_topology, decisiones_base)
        # Para munis acceso (códigos 1-799)
        codes_access = df_topology[df_topology["tier"] == "acceso"]["codigo"]
        sub = df[df["codigo"].isin(codes_access)]
        assert (sub["tipo_punto_acceso"] == "armario_calle").all()
        assert (sub["capex_extra"] == 5000).all()
        assert (sub["opex_extra_anual"] == 0.0).all()

    def test_mixto_classifies_by_threshold(self, df_topology, decisiones_base):
        # Forzar tipo='mixto' con umbral 20.000 hab.
        cfg = dict(decisiones_base)
        cfg["infraestructura_acceso"] = dict(cfg["infraestructura_acceso"])
        cfg["infraestructura_acceso"]["tipo_punto_acceso"] = "mixto"
        cfg["infraestructura_acceso"]["umbral_hab_para_local_cerrado"] = 20000

        df = infraestructura_acceso_por_municipio(df_topology, cfg)
        merged = df.merge(df_topology[["codigo", "hab", "tier"]], on="codigo", how="left")
        # Filtrar sólo acceso
        sub = merged[merged["tier"] == "acceso"]
        # Munis con hab >= 20.000 → local_cerrado, hab < 20.000 → armario_calle
        big = sub[sub["hab"] >= 20000]
        small = sub[sub["hab"] < 20000]
        if not big.empty:
            assert (big["tipo_punto_acceso"] == "local_cerrado").all()
        if not small.empty:
            assert (small["tipo_punto_acceso"] == "armario_calle").all()


# ---------------------------------------------------------------------------
# municipal_viability
# ---------------------------------------------------------------------------

class TestMunicipalViability:

    def test_900_rows(self, df_topology, parametros, decisiones_base):
        df_a = traffic_abast(df_topology, decisiones_base)
        df_m = traffic_mayorista(df_topology, decisiones_base, año=20)
        df_v = municipal_viability(df_topology, df_a, df_m, parametros, decisiones_base)
        assert len(df_v) == 900

    def test_abast_revenue_total(self, df_topology, parametros, decisiones_base):
        # 5000 sedes × 1000 €/mes × 12 = 60 M€/año
        df_a = traffic_abast(df_topology, decisiones_base)
        df_m = traffic_mayorista(df_topology, decisiones_base, año=20)
        df_v = municipal_viability(df_topology, df_a, df_m, parametros, decisiones_base)
        assert df_v["ingresos_abast_anuales"].sum() == pytest.approx(60_000_000, rel=1e-6)

    def test_a900_highest_score(self, df_topology, parametros, decisiones_base):
        df_a = traffic_abast(df_topology, decisiones_base)
        df_m = traffic_mayorista(df_topology, decisiones_base, año=20)
        df_v = municipal_viability(df_topology, df_a, df_m, parametros, decisiones_base)
        # A900 (769 sedes ABAST + 2M habitantes) debe sacar el score máximo.
        top = df_v.nlargest(1, "score_atractivo").iloc[0]
        assert top["municipio"] == "A900"


# ---------------------------------------------------------------------------
# deployment_priority_order
# ---------------------------------------------------------------------------

class TestDeploymentPriority:

    def test_a900_first_with_ingresos_descendente(
        self, df_topology, parametros, decisiones_base,
    ):
        df_a = traffic_abast(df_topology, decisiones_base)
        df_m = traffic_mayorista(df_topology, decisiones_base, año=20)
        df_v = municipal_viability(df_topology, df_a, df_m, parametros, decisiones_base)
        df_o = deployment_priority_order(df_v, decisiones_base)
        # base: criterio='ingresos_potenciales_descendente', arrancar_por='A900'
        assert df_o.iloc[0]["municipio"] == "A900"
        assert df_o.iloc[0]["orden_despliegue"] == 1

    def test_900_rows(self, df_topology, parametros, decisiones_base):
        df_a = traffic_abast(df_topology, decisiones_base)
        df_m = traffic_mayorista(df_topology, decisiones_base, año=20)
        df_v = municipal_viability(df_topology, df_a, df_m, parametros, decisiones_base)
        df_o = deployment_priority_order(df_v, decisiones_base)
        assert len(df_o) == 900

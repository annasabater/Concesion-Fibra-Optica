"""Tests para src/load.py — happy path según el spec del prompt 01.

Estos tests asumen que los archivos reales están en `data/`:
    - data/topologia_municipios.xlsx (o como lo hayas nombrado)
    - data/parametros_economicos.xlsx (puede ser el mismo archivo que el anterior)
    - data/decisiones.yaml

Si tu nombre de archivo difiere, ajusta las constantes TOPOLOGY_FILE y
PARAMETERS_FILE en este módulo.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.load import load_topology, load_parameters, load_decisiones


# ---------------------------------------------------------------------------
# Configuración de paths (ajustar si tus archivos se llaman distinto)
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent.parent / "data"

# Si el Excel del profe es un único archivo con todas las hojas (caso real
# observado), usar el mismo path para topology y parámetros.
TOPOLOGY_FILE = DATA_DIR / "topologia_municipios.xlsx"
PARAMETERS_FILE = DATA_DIR / "parametros_economicos.xlsx"
DECISIONES_FILE = DATA_DIR / "decisiones.yaml"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def df_topology():
    """Carga la topología una vez por módulo (la lectura del Excel es cara)."""
    if not TOPOLOGY_FILE.exists():
        pytest.skip(f"No existe {TOPOLOGY_FILE}; salta los tests de topología.")
    return load_topology(TOPOLOGY_FILE)


@pytest.fixture(scope="module")
def parameters():
    if not PARAMETERS_FILE.exists():
        pytest.skip(f"No existe {PARAMETERS_FILE}; salta los tests de parámetros.")
    return load_parameters(PARAMETERS_FILE)


# ---------------------------------------------------------------------------
# Tests de load_topology
# ---------------------------------------------------------------------------

class TestTopology:

    def test_900_rows(self, df_topology):
        assert len(df_topology) == 900

    def test_codigo_complete_range(self, df_topology):
        assert set(df_topology["codigo"]) == set(range(1, 901))

    def test_codigo_no_duplicates(self, df_topology):
        assert df_topology["codigo"].is_unique

    def test_total_sedes_abast(self, df_topology):
        assert df_topology["sedes_abast"].sum() == 5_000

    def test_total_habitantes(self, df_topology):
        assert df_topology["hab"].sum() == 8_590_900

    def test_tier_distribution(self, df_topology):
        counts = df_topology["tier"].value_counts().to_dict()
        assert counts == {"acceso": 799, "agregacion": 91, "troncal": 10}

    def test_num_operadores_in_range(self, df_topology):
        assert df_topology["num_operadores"].between(1, 5).all()

    def test_km_non_negative(self, df_topology):
        assert (df_topology["km"] >= 0).all()

    def test_a900_is_central_hub(self, df_topology):
        a900 = df_topology[df_topology["codigo"] == 900].iloc[0]
        assert a900["tier"] == "troncal"
        # A900 está en los 3 anillos troncales
        assert "T1" in a900["anillo_troncal"]
        assert "T2" in a900["anillo_troncal"]
        assert "T3" in a900["anillo_troncal"]
        # Y en agregación A1+A2
        assert "A1" in a900["anillo_agregacion"]
        assert "A2" in a900["anillo_agregacion"]

    def test_acceso_nodes_have_destino(self, df_topology):
        """Casi todos los nodos de acceso deben tener destino_acceso poblado."""
        acceso = df_topology[df_topology["tier"] == "acceso"]
        # Permitir hasta un 1% de huecos por si hay artefactos del Excel
        sin_destino = acceso["destino_acceso"].isna().sum()
        assert sin_destino < len(acceso) * 0.01

    def test_terminator_nodes_have_no_destino(self, df_topology):
        """Códigos 800–900 son terminadores: destino_acceso debe ser None."""
        terminadores = df_topology[df_topology["codigo"] >= 800]
        assert terminadores["destino_acceso"].isna().all()

    def test_tier_codigo_consistency(self, df_topology):
        """Por convención: 1–799 acceso, 800–890 agregación, 891–900 troncal."""
        for tier, (lo, hi) in {
            "acceso":     (1, 799),
            "agregacion": (800, 890),
            "troncal":    (891, 900),
        }.items():
            sub = df_topology[df_topology["codigo"].between(lo, hi)]
            assert (sub["tier"] == tier).all(), (
                f"Códigos {lo}–{hi} deberían tener tier='{tier}'"
            )


# ---------------------------------------------------------------------------
# Tests de load_parameters
# ---------------------------------------------------------------------------

class TestParameters:

    def test_three_categories(self, parameters):
        assert set(parameters.keys()) == {"ingresos", "opex", "capex"}

    def test_ingresos_values(self, parameters):
        assert parameters["ingresos"]["alta_abast"] == 0
        assert parameters["ingresos"]["recurrente_abast"] == 1000
        assert parameters["ingresos"]["alta_mayorista"] == 1500
        assert parameters["ingresos"]["recurrente_mayorista"] == 700

    def test_capex_values(self, parameters):
        assert parameters["capex"]["alta_sede_abast"] == 20_000
        assert parameters["capex"]["alta_sede_mayorista"] == 20_000
        assert parameters["capex"]["obra_civil_acceso_eur_m"] == 100
        assert parameters["capex"]["nodo_chasis"] == 100_000
        assert parameters["capex"]["equipo_cliente"] == 300
        assert parameters["capex"]["equipo_agreg_10p"] == 1_500
        assert parameters["capex"]["equipo_agreg_20p"] == 5_000
        assert parameters["capex"]["equipo_agreg_40p"] == 12_000
        assert parameters["capex"]["equipo_troncal_mpls"] == 50_000
        assert parameters["capex"]["equipo_troncal_optico_40l"] == 60_000

    def test_opex_values(self, parameters):
        assert parameters["opex"]["mant_fibra_eur_km_año"] == 250
        assert parameters["opex"]["mant_equipos_pct_capex"] == pytest.approx(0.10)
        assert parameters["opex"]["derechos_paso_pct_ingresos"] == pytest.approx(0.03)
        assert parameters["opex"]["costes_ventas_mayorista_pct"] == pytest.approx(0.10)
        assert parameters["opex"]["gastos_generales_anuales"] == 700_000


# ---------------------------------------------------------------------------
# Tests de load_decisiones
# ---------------------------------------------------------------------------

class TestDecisiones:

    @pytest.fixture(autouse=True)
    def skip_if_no_yaml(self):
        if not DECISIONES_FILE.exists():
            pytest.skip(f"No existe {DECISIONES_FILE}; salta los tests de decisiones.")

    def test_base_loads(self):
        cfg = load_decisiones(DECISIONES_FILE, "base")
        assert isinstance(cfg, dict)
        assert "mayorista" in cfg
        assert "abast" in cfg
        assert "equipos" in cfg
        assert "despliegue" in cfg
        assert "descuento" in cfg

    def test_base_contents(self):
        cfg = load_decisiones(DECISIONES_FILE, "base")
        assert cfg["mayorista"]["cuota_mercado"]["tipo"] in {"rampa", "equilibrio", "agresivo"}
        assert cfg["abast"]["bw_por_sede_mbps"] == 100
        assert cfg["abast"]["overbooking"] == 1
        assert isinstance(cfg["descuento"]["tasa"], (int, float))
        assert 0 < cfg["descuento"]["tasa"] < 1

    def test_optimista_inherits_from_base(self):
        """Optimista debe heredar bw_por_hogar_mbps de base sin tener que repetirlo."""
        base = load_decisiones(DECISIONES_FILE, "base")
        opt = load_decisiones(DECISIONES_FILE, "optimista")
        assert opt["mayorista"]["bw_por_hogar_mbps"] == base["mayorista"]["bw_por_hogar_mbps"]
        assert opt["mayorista"]["habitantes_por_hogar"] == base["mayorista"]["habitantes_por_hogar"]
        assert opt["abast"]["bw_por_sede_mbps"] == base["abast"]["bw_por_sede_mbps"]

    def test_optimista_overrides_alpha(self):
        """Optimista debe tener alpha_objetivo distinto al de base."""
        base = load_decisiones(DECISIONES_FILE, "base")
        opt = load_decisiones(DECISIONES_FILE, "optimista")
        assert opt["mayorista"]["cuota_mercado"]["alpha_objetivo"] != \
               base["mayorista"]["cuota_mercado"]["alpha_objetivo"]
        assert opt["mayorista"]["cuota_mercado"]["alpha_objetivo"] > \
               base["mayorista"]["cuota_mercado"]["alpha_objetivo"]

    def test_pesimista_overrides_alpha(self):
        base = load_decisiones(DECISIONES_FILE, "base")
        pes = load_decisiones(DECISIONES_FILE, "pesimista")
        assert pes["mayorista"]["cuota_mercado"]["alpha_objetivo"] < \
               base["mayorista"]["cuota_mercado"]["alpha_objetivo"]

    def test_invalid_scenario_raises(self):
        with pytest.raises(ValueError):
            load_decisiones(DECISIONES_FILE, "no_existe")

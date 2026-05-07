"""main.py — orquestador end-to-end del pipeline ABAST.

Ejecuta las 10 fases del cálculo (load → topology → traffic → equipment →
capex → opex → revenue → pnl → visualize → report) para un escenario
del fichero `data/decisiones.yaml`. Cada fase pendiente se loguea con
WARNING y el pipeline continúa, de forma que el orquestador es ejecutable
desde el setup inicial (todos los stubs raisean NotImplementedError).
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src import (
    capex,
    equipment,
    load,
    opex,
    pnl,
    report,
    revenue,
    topology,
    traffic,
    visualize,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_OUTPUT_DIR = ROOT / "outputs"
TOPOLOGY_FILENAME = "Despliegue de REd Municipios 2026.xlsx"
DECISIONES_FILENAME = "decisiones.yaml"


def main(
    escenario: str = "base",
    data_dir: Path = DEFAULT_DATA_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> None:
    """Orquesta las 10 fases del pipeline para un escenario.

    Args:
        escenario: nombre del escenario en decisiones.yaml.
        data_dir: ruta a la carpeta data/.
        output_dir: ruta base de outputs/. Los artefactos van a
            output_dir/escenario_<nombre>/.
    """
    out = output_dir / f"escenario_{escenario}"
    out.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("Pipeline ABAST | escenario=%s", escenario)
    logger.info("data_dir=%s", data_dir)
    logger.info("output_dir=%s", out)
    logger.info("=" * 60)

    # ---- FASE 1 — load ----
    logger.info("[1/10] load: leyendo Excel y decisiones.yaml...")
    df = load.load_topology(data_dir / TOPOLOGY_FILENAME)
    parametros = load.load_parameters(data_dir / TOPOLOGY_FILENAME)
    decisiones = load.load_decisiones(data_dir / DECISIONES_FILENAME, escenario)

    # ---- FASE 2 — topology ----
    logger.info("[2/10] topology: construyendo grafo (root=A900)...")
    graph = topology.build_graph(df)
    stats = topology.stats_by_ring(graph)
    stats.to_csv(out / "stats_by_ring.csv", index=False)
    logger.info("Stats por anillo guardadas en %s", out / "stats_by_ring.csv")

    # ---- FASE 3 — traffic ----
    logger.info("[3/10] traffic: tráfico ABAST + mayorista...")
    traffic_df = None
    try:
        traffic_df = traffic.compute_traffic(df, decisiones)
    except NotImplementedError as e:
        logger.warning("traffic pendiente: %s", e)

    # ---- FASE 4 — equipment ----
    logger.info("[4/10] equipment: tráfico acumulado + selección de equipos...")
    equipment_df = None
    try:
        equipment_df = equipment.assign_equipment(graph, traffic_df, decisiones)
    except NotImplementedError as e:
        logger.warning("equipment pendiente: %s", e)

    # ---- FASE 5 — capex ----
    logger.info("[5/10] capex: inversiones por año y por anillo...")
    capex_df = None
    try:
        capex_df = capex.compute_capex(df, equipment_df, decisiones, parametros)
    except NotImplementedError as e:
        logger.warning("capex pendiente: %s", e)

    # ---- FASE 6 — opex ----
    logger.info("[6/10] opex: costes operativos plurianuales...")
    opex_df = None
    try:
        opex_df = opex.compute_opex(capex_df, df, decisiones, parametros)
    except NotImplementedError as e:
        logger.warning("opex pendiente: %s", e)

    # ---- FASE 7 — revenue ----
    logger.info("[7/10] revenue: ingresos plurianuales...")
    revenue_df = None
    try:
        revenue_df = revenue.compute_revenue(df, decisiones, parametros)
    except NotImplementedError as e:
        logger.warning("revenue pendiente: %s", e)

    # ---- FASE 8 — pnl ----
    logger.info("[8/10] pnl: cuenta de resultados + KPIs (NPV, IRR, payback)...")
    pnl_df = None
    try:
        pnl_df = pnl.compute_pnl(capex_df, opex_df, revenue_df, decisiones)
    except NotImplementedError as e:
        logger.warning("pnl pendiente: %s", e)

    # ---- FASE 9 — visualize ----
    logger.info("[9/10] visualize: diagramas de topología y gráficas...")
    if graph is not None:
        written = visualize.generate_diagrams(graph, df, out)
        logger.info("Generadas %d imágenes (PNG+SVG) en %s/img/",
                    len(written), out)

    # ---- FASE 10 — report ----
    logger.info("[10/10] report: Excel y PDFs de la oferta...")
    try:
        report.generate_reports(
            pnl_df, capex_df, opex_df, revenue_df, out, decisiones,
        )
    except NotImplementedError as e:
        logger.warning("report pendiente: %s", e)

    logger.info("=" * 60)
    logger.info("Pipeline ABAST | escenario=%s | OK", escenario)
    logger.info("=" * 60)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Orquestador del pipeline ABAST (concesión fibra óptica 20 años).",
    )
    parser.add_argument(
        "--escenario", default="base",
        help="Nombre del escenario en decisiones.yaml (default: base).",
    )
    parser.add_argument(
        "--data-dir", type=Path, default=DEFAULT_DATA_DIR,
        help=f"Ruta a data/ (default: {DEFAULT_DATA_DIR}).",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help=f"Ruta base de outputs/ (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Nivel de logging (default: INFO).",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    main(args.escenario, args.data_dir, args.output_dir)

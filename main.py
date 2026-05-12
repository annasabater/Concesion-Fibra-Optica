"""main.py — orquestador end-to-end del pipeline ABAST.

Ejecuta las 11 fases del cálculo (load → topology → traffic → geomarketing
→ equipment → capex → opex → revenue → pnl → visualize → report) para un
escenario del fichero `data/decisiones.yaml`. Cada fase pendiente se loguea
con WARNING y el pipeline continúa, de forma que el orquestador es
ejecutable desde el setup inicial (los stubs raisean NotImplementedError).
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src import (
    capex,
    equipment,
    geomarketing,
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
    """Orquesta las 11 fases del pipeline para un escenario.

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
    logger.info("[1/11] load: leyendo Excel y decisiones.yaml...")
    df = load.load_topology(data_dir / TOPOLOGY_FILENAME)
    parametros = load.load_parameters(data_dir / TOPOLOGY_FILENAME)
    decisiones = load.load_decisiones(data_dir / DECISIONES_FILENAME, escenario)

    # ---- FASE 2 — topology ----
    logger.info("[2/11] topology: construyendo grafo (root=A900)...")
    graph = topology.build_graph(df)
    stats = topology.stats_by_ring(graph)
    stats.to_csv(out / "stats_by_ring.csv", index=False)
    logger.info("Stats por anillo guardadas en %s", out / "stats_by_ring.csv")

    # ---- FASE 3 — traffic ----
    logger.info("[3/11] traffic: tráfico ABAST + mayorista (año 20)...")
    traffic_df = traffic.compute_traffic(df, decisiones, año=20)
    traffic_df.to_csv(out / "traffic_per_muni.csv", index=False)
    # Tráfico ABAST y mayorista por separado (para análisis y validación).
    df_abast = traffic.traffic_abast(df, decisiones)
    df_mayo = traffic.traffic_mayorista(df, decisiones, año=20)
    df_abast.to_csv(out / "traffic_abast.csv", index=False)
    df_mayo.to_csv(out / "traffic_mayorista_anio20.csv", index=False)

    # ---- FASE 4 — geomarketing ----
    logger.info("[4/11] geomarketing: viabilidad por muni + orden despliegue...")
    df_pyme = geomarketing.pyme_estimation_per_municipality(df, decisiones)
    df_infra = geomarketing.infraestructura_acceso_por_municipio(df, decisiones)
    df_viab = geomarketing.municipal_viability(
        df, df_abast, df_mayo, parametros, decisiones,
    )
    df_orden = geomarketing.deployment_priority_order(df_viab, decisiones)
    df_pyme.to_csv(out / "pymes_per_muni.csv", index=False)
    df_infra.to_csv(out / "infraestructura_acceso_per_muni.csv", index=False)
    df_viab.to_csv(out / "municipal_viability.csv", index=False)
    df_orden.to_csv(out / "deployment_priority.csv", index=False)
    n_viables = int(df_viab["viable"].sum())
    logger.info(
        "geomarketing: %d/900 municipios viables; "
        "ingresos potenciales=%.1f M€/año.",
        n_viables, df_viab["ingresos_total_anuales"].sum() / 1e6,
    )

    # ---- FASE 5 — equipment ----
    logger.info("[5/11] equipment: tráfico acumulado + selección de equipos...")
    equipment_df = equipment.assign_equipment(graph, traffic_df, decisiones, parametros)
    equipment_df.to_csv(out / "equipment_per_node.csv", index=False)
    capex_totals = equipment.total_capex_equipos(equipment_df)
    logger.info(
        "CAPEX equipos = %.2f M€ (cliente=%.1f, agregación=%.1f, "
        "troncal=%.1f, chasis=%.1f, DC=%.1f)",
        capex_totals["total"] / 1e6,
        capex_totals["equipo_cliente"] / 1e6,
        capex_totals["equipo_agregacion"] / 1e6,
        capex_totals["equipo_troncal"] / 1e6,
        capex_totals["chasis"] / 1e6,
        capex_totals["datacenter_a900"] / 1e6,
    )

    # Tràfic per anell (taula + gràfic)
    df_traffic_ring = topology.traffic_by_ring(graph, traffic_df)
    df_traffic_ring.to_csv(out / "traffic_by_ring.csv", index=False)
    img_dir = out / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    visualize.plot_traffic_by_ring(df_traffic_ring, img_dir / "traffic_by_ring")
    logger.info("Tràfic per anell guardat a %s", out / "traffic_by_ring.csv")

    # ---- FASE 6 — capex ----
    logger.info("[6/11] capex: inversiones por año y por anillo...")
    capex_df = None
    try:
        capex_df = capex.compute_capex(df, equipment_df, decisiones, parametros)
    except NotImplementedError as e:
        logger.warning("capex pendiente: %s", e)

    # ---- FASE 7 — opex ----
    logger.info("[7/11] opex: costes operativos plurianuales...")
    opex_df = None
    try:
        opex_df = opex.compute_opex(capex_df, df, decisiones, parametros)
    except NotImplementedError as e:
        logger.warning("opex pendiente: %s", e)

    # ---- FASE 8 — revenue ----
    logger.info("[8/11] revenue: ingresos plurianuales...")
    revenue_df = None
    try:
        revenue_df = revenue.compute_revenue(df, decisiones, parametros)
    except NotImplementedError as e:
        logger.warning("revenue pendiente: %s", e)

    # ---- FASE 9 — pnl ----
    logger.info("[9/11] pnl: cuenta de resultados + KPIs (NPV, IRR, payback)...")
    pnl_df = None
    try:
        pnl_df = pnl.compute_pnl(capex_df, opex_df, revenue_df, decisiones)
    except NotImplementedError as e:
        logger.warning("pnl pendiente: %s", e)

    # ---- FASE 10 — visualize ----
    logger.info("[10/11] visualize: diagramas de topología y gráficas...")
    if graph is not None:
        written = visualize.generate_diagrams(graph, df, out)
        logger.info("Generadas %d imágenes (PNG+SVG) en %s/img/",
                    len(written), out)

    # ---- FASE 11 — report ----
    logger.info("[11/11] report: Excel y PDFs de la oferta...")
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
        help="Nombre del escenario en decisiones.yaml (default: base). "
             "Usa 'todos' para ejecutar base+optimista+pesimista.",
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
    if args.escenario == "todos":
        for esc in ("pesimista", "base", "optimista"):
            main(esc, args.data_dir, args.output_dir)
    else:
        main(args.escenario, args.data_dir, args.output_dir)

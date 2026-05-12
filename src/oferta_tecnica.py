"""oferta_tecnica.py — PDF de la oferta técnica para TAREA 5 (12/05/2026).

Compone un PDF (~10-15 páginas) con los 5 bloques de la entrega:
    1. Dimensionamiento de tráfico
    2. Selección de equipo
    3. Decisiones defendidas
    4. Análisis geomarketing
    5. Hallazgos clave (SPOF A900, espina dorsal A2)

Lee los CSVs ya generados en `outputs/escenario_*/` por main.py y los
diagramas en `outputs/escenario_base/img/`. Genera además dos gráficas
comparativas propias (BW total y CAPEX por escenario).

Uso:
    python -m src.oferta_tecnica                      # base (default)
    python -m src.oferta_tecnica --escenario optimista
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT / "outputs"
DEFAULT_DATA_DIR = ROOT / "data"

ESCENARIOS = ("pesimista", "base", "optimista")


# ---------------------------------------------------------------------------
# Carga de datos ya generados por main.py
# ---------------------------------------------------------------------------

def _load_scenario_outputs(out_root: Path, escenario: str) -> dict:
    """Carga los CSVs de un escenario en un dict de DataFrames."""
    base = out_root / f"escenario_{escenario}"
    return {
        "traffic": pd.read_csv(base / "traffic_per_muni.csv"),
        "viability": pd.read_csv(base / "municipal_viability.csv"),
        "deployment": pd.read_csv(base / "deployment_priority.csv"),
        "equipment": pd.read_csv(base / "equipment_per_node.csv"),
        "stats_ring": pd.read_csv(base / "stats_by_ring.csv"),
    }


def _load_decisiones_yaml(path: Path, escenario: str) -> dict:
    """Carga la sección de un escenario sin hacer deep merge (para mostrar
    los overrides explícitos)."""
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return raw.get("escenarios", {}).get(escenario, {})


# ---------------------------------------------------------------------------
# Gráficas comparativas (se guardan en outputs/oferta_tecnica/)
# ---------------------------------------------------------------------------

def _build_comparative_charts(
    scenarios_data: dict[str, dict],
    output_dir: Path,
) -> dict[str, Path]:
    """Genera dos PNG: barras de BW total y CAPEX equipos por escenario."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    # --- BW total por escenario, desglosado ABAST/Mayorista ---
    bw_abast, bw_mayo, capex_total = [], [], []
    for esc in ESCENARIOS:
        t = scenarios_data[esc]["traffic"]
        e = scenarios_data[esc]["equipment"]
        bw_abast.append(t["bw_abast_mbps"].sum() / 1000)
        bw_mayo.append(t["bw_mayorista_mbps"].sum() / 1000)
        capex_total.append(
            (e["capex_equipo"].sum() + e["capex_chasis"].sum()
             + e["capex_extra"].sum() + e["equipo_cliente_capex"].sum())
            / 1e6
        )

    fig, ax = plt.subplots(figsize=(7, 4))
    x = range(len(ESCENARIOS))
    ax.bar(x, bw_abast, label="ABAST (autoprestación)", color="#2874a6")
    ax.bar(x, bw_mayo, bottom=bw_abast, label="Mayorista (residencial+PYME)",
           color="#5dade2")
    ax.set_xticks(list(x))
    ax.set_xticklabels([e.capitalize() for e in ESCENARIOS])
    ax.set_ylabel("Tráfico territorial año 20 (Gbps)")
    ax.set_title("Dimensionamiento de tráfico por escenario")
    ax.legend(loc="upper left")
    for i, (a, m) in enumerate(zip(bw_abast, bw_mayo)):
        ax.text(i, a + m + 80, f"{a + m:.0f}", ha="center", fontsize=9,
                fontweight="bold")
    fig.tight_layout()
    paths["bw"] = output_dir / "bw_por_escenario.png"
    fig.savefig(paths["bw"], dpi=150, bbox_inches="tight")
    plt.close(fig)

    # --- CAPEX equipos por escenario ---
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(x, capex_total, color=["#c0392b", "#2874a6", "#27ae60"])
    ax.set_xticks(list(x))
    ax.set_xticklabels([e.capitalize() for e in ESCENARIOS])
    ax.set_ylabel("CAPEX equipos (M€)")
    ax.set_title("CAPEX de equipos por escenario")
    for i, c in enumerate(capex_total):
        ax.text(i, c + 0.1, f"{c:.2f} M€", ha="center", fontsize=10,
                fontweight="bold")
    fig.tight_layout()
    paths["capex"] = output_dir / "capex_por_escenario.png"
    fig.savefig(paths["capex"], dpi=150, bbox_inches="tight")
    plt.close(fig)

    return paths


# ---------------------------------------------------------------------------
# Helpers de estilos PDF
# ---------------------------------------------------------------------------

def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontSize=22, leading=26,
            textColor=colors.HexColor("#1a5490"), spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"], fontSize=12,
            textColor=colors.HexColor("#5d6d7e"), spaceAfter=6,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontSize=15,
            textColor=colors.HexColor("#1a5490"), spaceBefore=10, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontSize=12,
            textColor=colors.HexColor("#21618c"), spaceBefore=6, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontSize=10, leading=13,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"], fontSize=8,
            textColor=colors.HexColor("#5d6d7e"),
        ),
        "key": ParagraphStyle(
            "key", parent=base["BodyText"], fontSize=10, leading=13,
            backColor=colors.HexColor("#fef9e7"),
            borderColor=colors.HexColor("#f1c40f"),
            borderWidth=1, borderPadding=8, spaceAfter=8,
        ),
    }


_TABLE_STYLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5490")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ("ALIGN", (0, 1), (0, -1), "LEFT"),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1),
     [colors.whitesmoke, colors.HexColor("#ebf5fb")]),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bdc3c7")),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
])


def _table(data: list[list], col_widths: list[float] | None = None) -> Table:
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(_TABLE_STYLE)
    return t


# ---------------------------------------------------------------------------
# Bloques del PDF
# ---------------------------------------------------------------------------

def _block_cover(styles: dict, escenario: str) -> list:
    return [
        Spacer(1, 4 * cm),
        Paragraph("Proyecto ABAST", styles["title"]),
        Paragraph(
            "Concesión a 20 años de red de fibra óptica",
            styles["subtitle"],
        ),
        Spacer(1, 0.6 * cm),
        Paragraph("<b>Oferta técnica — TAREA 5</b>", styles["h1"]),
        Paragraph("Equipos y solución técnica", styles["subtitle"]),
        Spacer(1, 1.5 * cm),
        Paragraph(
            f"<b>Escenario defendido:</b> {escenario}<br/>"
            f"<b>Fecha de entrega:</b> 12 de mayo de 2026<br/>"
            f"<b>Fecha del documento:</b> {date.today().isoformat()}",
            styles["body"],
        ),
        Spacer(1, 6 * cm),
        Paragraph(
            "Master en Ingeniería de Telecomunicaciones — La Salle URL<br/>"
            "Projectes de Xarxes i Sistemes de Telecomunicació II",
            styles["small"],
        ),
        PageBreak(),
    ]


def _block_1_traffic(
    styles: dict,
    scenarios_data: dict[str, dict],
    chart_path: Path,
) -> list:
    flow = [
        Paragraph("1. Dimensionamiento de tráfico", styles["h1"]),
        Paragraph(
            "El tráfico territorial se calcula con la fórmula desglosada de la "
            "pizarra del 07/05/2026: el tráfico mayorista por municipio resulta "
            "del producto independiente de tres factores — hogares teóricos, "
            "cuota entre operadores y penetración de fibra. La separación de "
            "cuota y penetración permite analizar la sensibilidad a cada "
            "factor por separado y refleja la realidad de mercado.",
            styles["body"],
        ),
        Paragraph(
            "<b>Tráfico ABAST</b> = sedes_abast × 100 Mbps (overbooking 1:1)<br/>"
            "<b>Tráfico mayorista</b> = (hab/hab_por_hogar) × cuota_op × "
            "penetración × 100 Mbps / overbooking",
            styles["body"],
        ),
        Paragraph("Totales territoriales en año 20", styles["h2"]),
    ]
    rows = [["Escenario", "ABAST (Gbps)", "Mayorista (Gbps)",
             "Total (Gbps)", "BW en A900 (Gbps)"]]
    for esc in ESCENARIOS:
        t = scenarios_data[esc]["traffic"]
        e = scenarios_data[esc]["equipment"]
        bw_a900 = float(e.loc[e["municipio"] == "A900", "bw_acumulado_mbps"].iloc[0])
        rows.append([
            esc.capitalize(),
            f"{t['bw_abast_mbps'].sum() / 1000:,.1f}",
            f"{t['bw_mayorista_mbps'].sum() / 1000:,.1f}",
            f"{t['bw_total_mbps'].sum() / 1000:,.1f}",
            f"{bw_a900 / 1000:,.1f}",
        ])
    flow.append(_table(rows, [3.5 * cm, 3 * cm, 3.5 * cm, 3 * cm, 3.5 * cm]))
    flow.append(Spacer(1, 0.4 * cm))
    flow.append(Image(str(chart_path), width=15 * cm, height=8.5 * cm))
    flow.append(Paragraph(
        "<b>Sanity check:</b> ABAST = 5.000 sedes × 100 Mbps = 500 Gbps "
        "(constante en los 3 escenarios, sin overbooking). Mayorista escala con "
        "α_objetivo × penetración: 0,30×0,55=0,165 (pesimista) → 0,40×0,70=0,280 "
        "(base) → 0,50×0,85=0,425 (optimista).",
        styles["small"],
    ))
    flow.append(PageBreak())
    return flow


def _block_2_equipment(
    styles: dict,
    df_equipment: pd.DataFrame,
    capex_chart: Path,
) -> list:
    # Distribución por tier × equipo principal
    dist = (
        df_equipment.groupby(["tier", "equipo_principal"])
        .size().reset_index(name="n_nodos")
        .sort_values(["tier", "n_nodos"], ascending=[True, False])
    )
    rows = [["Tier", "Equipo principal", "Nº de nodos"]]
    for _, r in dist.iterrows():
        rows.append([r["tier"].capitalize(), r["equipo_principal"], int(r["n_nodos"])])

    # Resumen CAPEX equipos por categoría
    capex_cliente = float(df_equipment["equipo_cliente_capex"].sum())
    capex_agreg = float(
        df_equipment.loc[df_equipment["tier"] == "agregacion", "capex_equipo"].sum()
    )
    capex_troncal = float(
        df_equipment.loc[df_equipment["tier"] == "troncal", "capex_equipo"].sum()
    )
    capex_chasis = float(df_equipment["capex_chasis"].sum())
    capex_dc = float(df_equipment["capex_extra"].sum())
    capex_total = capex_cliente + capex_agreg + capex_troncal + capex_chasis + capex_dc

    capex_rows = [
        ["Categoría", "CAPEX (€)", "% del total"],
        ["Equipo cliente (300 €/sede)", f"{capex_cliente:,.0f}",
         f"{capex_cliente / capex_total * 100:.1f}%"],
        ["Equipo agregación (10p/20p/40p/MPLS)", f"{capex_agreg:,.0f}",
         f"{capex_agreg / capex_total * 100:.1f}%"],
        ["Equipo troncal (MPLS + óptico 40λ)", f"{capex_troncal:,.0f}",
         f"{capex_troncal / capex_total * 100:.1f}%"],
        ["Chasis nodos (100 k€/nodo)", f"{capex_chasis:,.0f}",
         f"{capex_chasis / capex_total * 100:.1f}%"],
        ["Datacenter A900 (extra)", f"{capex_dc:,.0f}",
         f"{capex_dc / capex_total * 100:.1f}%"],
        ["TOTAL", f"{capex_total:,.0f}", "100,0%"],
    ]

    return [
        Paragraph("2. Selección de equipo por nodo", styles["h1"]),
        Paragraph(
            "Tras calcular el tráfico acumulado por BFS desde las hojas hacia "
            "A900 (incluyendo el reenvío de los anillos de agregación a sus "
            "gateways y de los anillos troncales a A900), cada nodo recibe el "
            "equipo más pequeño que cumple <b>simultáneamente</b> el umbral de "
            "puertos (n_links contra los umbrales de decisiones.yaml) y la "
            "capacidad nominal en Mbps del equipo.",
            styles["body"],
        ),
        Paragraph("Distribución de equipos en el escenario base", styles["h2"]),
        _table(rows, [2.5 * cm, 9 * cm, 3 * cm]),
        Spacer(1, 0.4 * cm),
        Paragraph("CAPEX de equipos (escenario base)", styles["h2"]),
        _table(capex_rows, [8 * cm, 4.5 * cm, 3 * cm]),
        Spacer(1, 0.4 * cm),
        Image(str(capex_chart), width=15 * cm, height=8.5 * cm),
        PageBreak(),
    ]


def _block_3_decisions(
    styles: dict,
    decisiones_yaml: dict,
) -> list:
    """Render de las palancas clave defendidas en la oferta."""
    may = decisiones_yaml["mayorista"]
    abast = decisiones_yaml["abast"]
    eq = decisiones_yaml["equipos"]
    desp = decisiones_yaml["despliegue"]
    infra = decisiones_yaml["infraestructura_acceso"]
    dc = decisiones_yaml["datacenter_a900"]

    rows = [
        ["Palanca", "Valor base", "Justificación"],
        ["Estrategia cuota mayorista",
         may["cuota_mercado"]["tipo"],
         "Rampa α(t) capturando mercado progresivamente"],
        ["α objetivo (cuota entre operadores)",
         f"{may['cuota_mercado']['alpha_objetivo']:.2f}",
         "Compromiso entre conservador y ambicioso"],
        ["Años de rampa",
         str(may["cuota_mercado"]["anios_rampa"]),
         "Captura realista, no se llega al año 1 con cuota plena"],
        ["Penetración de fibra (residencial)",
         f"{may['penetracion_fibra_pct'] * 100:.0f}%",
         "Pizarra 07/05/2026 — mix urbano/rural"],
        ["BW comercial por hogar",
         f"{may['bw_por_hogar_mbps']} Mbps",
         "Producto wholesale residencial estándar"],
        ["Overbooking residencial",
         f"1:{int(may['overbooking'])}",
         "Estándar industria sin degradar SLA"],
        ["Overbooking ABAST",
         f"1:{int(abast['overbooking'])}",
         "Sedes públicas con BW garantizado"],
        ["Umbrales 10p / 20p / 40p (puertos)",
         f"{eq['umbral_10p_a_20p']} / {eq['umbral_20p_a_40p']} / {eq['umbral_40p_a_mpls']}",
         "Escalado en cascada por puertos y capacidad"],
        ["Redundancia equipos",
         eq["redundancia"],
         "1+1 sólo en troncal y A900 (CAPEX vs SLA)"],
        ["Estrategia de despliegue",
         desp["estrategia"],
         "Espina dorsal y ciudades primero, expansión radial"],
        ["Tope km/año",
         f"{desp['km_max_anuales']} km",
         "Cuello de botella obra civil + RRHH"],
        ["Punto de acceso",
         infra["tipo_punto_acceso"],
         "Armario de calle: CAPEX 5 k€ one-shot vs 8 k€/año alquiler"],
        ["CAPEX extra A900 (datacenter)",
         f"{dc['capex_extra']:,.0f} €",
         "CPD, NOC, salida internet pública, redundancia"],
    ]
    return [
        Paragraph("3. Decisiones técnicas defendidas", styles["h1"]),
        Paragraph(
            "Las palancas variables de la oferta viven en "
            "<i>data/decisiones.yaml</i> y se recalculan automáticamente sobre "
            "todo el pipeline. Este es el listado defendido en el escenario base; "
            "los escenarios optimista y pesimista heredan vía deep merge y sólo "
            "redefinen los valores de mayorista, despliegue y contingencia.",
            styles["body"],
        ),
        _table(rows, [5.5 * cm, 4.5 * cm, 7.5 * cm]),
        PageBreak(),
    ]


def _block_4_geomarketing(
    styles: dict,
    df_viab: pd.DataFrame,
    df_orden: pd.DataFrame,
) -> list:
    n_total = len(df_viab)
    n_viables = int(df_viab["viable"].sum())
    n_no_viables = n_total - n_viables
    ingresos_total = df_viab["ingresos_total_anuales"].sum() / 1e6

    top_orden = df_orden.head(10)
    orden_rows = [["Orden", "Muni", "Ingresos potenciales (€/año)",
                   "Año despliegue"]]
    for _, r in top_orden.iterrows():
        orden_rows.append([
            int(r["orden_despliegue"]),
            r["municipio"],
            f"{r['criterio_valor']:,.0f}",
            int(r["anio_objetivo_despliegue"]),
        ])

    top_score = df_viab.nlargest(5, "score_atractivo")[
        ["municipio", "hab", "sedes_abast", "ingresos_total_anuales",
         "payback_municipal_anios", "score_atractivo"]
    ]
    score_rows = [["Muni", "Hab", "Sedes ABAST", "Ingresos (€/año)",
                   "Payback (años)", "Score"]]
    for _, r in top_score.iterrows():
        score_rows.append([
            r["municipio"],
            f"{int(r['hab']):,}",
            int(r["sedes_abast"]),
            f"{r['ingresos_total_anuales']:,.0f}",
            "∞" if r["payback_municipal_anios"] == float("inf")
            else f"{r['payback_municipal_anios']:.1f}",
            f"{r['score_atractivo']:.1f}",
        ])

    return [
        Paragraph("4. Análisis geomarketing", styles["h1"]),
        Paragraph(
            "Para cada uno de los 900 municipios calculamos ingresos "
            "potenciales (ABAST + mayorista residencial + PYMEs estimadas), "
            "CAPEX local, OPEX local, payback municipal y un score combinado "
            "0–100. El flag de viabilidad es informativo: aunque un municipio "
            "no sea rentable, hay que conectarlo igual porque la cobertura es "
            "obligatoria al 100% según las bases del concurso.",
            styles["body"],
        ),
        Paragraph("Resumen de viabilidad", styles["h2"]),
        _table(
            [["Total munis", "Viables", "No viables",
              "Ingresos potenciales totales (M€/año)"],
             [n_total, n_viables, n_no_viables, f"{ingresos_total:,.1f}"]],
            [3 * cm, 3 * cm, 3 * cm, 7 * cm],
        ),
        Spacer(1, 0.4 * cm),
        Paragraph("Top 5 munis por score de atractivo", styles["h2"]),
        _table(score_rows, [2 * cm, 2.5 * cm, 2.2 * cm, 3.5 * cm, 2.6 * cm, 2 * cm]),
        Spacer(1, 0.4 * cm),
        Paragraph("Top 10 del orden de despliegue (criterio: ingresos descendente)",
                  styles["h2"]),
        _table(orden_rows, [1.8 * cm, 2.2 * cm, 6 * cm, 3 * cm]),
        PageBreak(),
    ]


def _block_5_findings(
    styles: dict,
    df_equipment: pd.DataFrame,
    img_anillos: Path,
    img_a2: Path,
) -> list:
    bw_a900 = float(
        df_equipment.loc[df_equipment["municipio"] == "A900", "bw_acumulado_mbps"].iloc[0]
    ) / 1000
    bw_a800 = float(
        df_equipment.loc[df_equipment["municipio"] == "A800", "bw_acumulado_mbps"].iloc[0]
    ) / 1000

    flow = [
        Paragraph("5. Hallazgos clave para la defensa", styles["h1"]),
        Paragraph(
            f"<b>Hallazgo 1 — A900 es SPOF crítico ({bw_a900:,.1f} Gbps):</b> "
            "el 100% del tráfico territorial converge en A900, que es a la vez "
            "datacenter del operador, NOC y punto de salida a internet pública "
            "para los clientes mayoristas. Justifica los 5 M€ extra de CAPEX "
            "específico (energía, refrigeración, seguridad, IT) y la decisión "
            "de redundancia 1+1 en troncal y A900.",
            styles["key"],
        ),
        Paragraph(
            f"<b>Hallazgo 2 — A2 es la espina dorsal ({bw_a800:,.1f} Gbps en A800):</b> "
            "del análisis de la topología, el 88% de los municipios de acceso "
            "(793 de 900) resuelven a través del anillo A2. Es deliberado del "
            "diseño que recibimos. A800 (gateway de A2) acumula >600 Gbps y "
            "necesita MPLS + 17 cajas 40p en paralelo + óptico 40λ. Es el "
            "segundo punto de fallo más crítico tras A900.",
            styles["key"],
        ),
        Paragraph(
            "<b>Hallazgo 3 — sensibilidad α × penetración:</b> el rango de "
            "ingresos entre escenarios (5,3 M€/año pesimista → 7,5 M€/año "
            "optimista) está dominado por el producto cuota×penetración. "
            "La separación explícita de los dos factores que pidió el profesor "
            "el 07/05 permite atribuir el riesgo correctamente: penetración "
            "es factor exógeno (mercado), cuota es decisión propia. Esto es "
            "decisivo para la negociación del reequilibrio LCSP.",
            styles["key"],
        ),
        Paragraph("Topología completa (anillos troncal + agregación)", styles["h2"]),
        Image(str(img_anillos), width=15 * cm, height=15 * cm),
        PageBreak(),
        Paragraph("Detalle del anillo A2 (espina dorsal)", styles["h2"]),
        Paragraph(
            "A2 cuelga de A900 y agrega 793 de los 900 municipios. Es el anillo "
            "que más equipo de respaldo necesita y el que primero hay que "
            "iluminar en el plan de despliegue.",
            styles["body"],
        ),
        Image(str(img_a2), width=15 * cm, height=15 * cm),
    ]
    return flow


# ---------------------------------------------------------------------------
# Compositor principal
# ---------------------------------------------------------------------------

def generate_oferta_tecnica_pdf(
    escenario: str = "base",
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    data_dir: Path = DEFAULT_DATA_DIR,
) -> Path:
    """Compone el PDF de oferta técnica para el escenario dado.

    Args:
        escenario: escenario defendido (base | optimista | pesimista).
        output_dir: ruta base de outputs/.
        data_dir: ruta a data/ (para leer decisiones.yaml).

    Returns:
        Path al PDF generado.
    """
    # Carga de los 3 escenarios para tablas comparativas.
    scenarios_data = {
        esc: _load_scenario_outputs(output_dir, esc) for esc in ESCENARIOS
    }
    decisiones_yaml = _load_decisiones_yaml(
        data_dir / "decisiones.yaml", escenario,
    )
    # Si el escenario es optimista/pesimista, completar con base para el
    # bloque de decisiones (deep merge ligero por palanca).
    base_yaml = _load_decisiones_yaml(data_dir / "decisiones.yaml", "base")
    decisiones_yaml = _shallow_merge(base_yaml, decisiones_yaml)

    # Gráficas comparativas.
    out_oferta = output_dir / "oferta_tecnica"
    chart_paths = _build_comparative_charts(scenarios_data, out_oferta)

    # Imágenes de la topología (ya existen en outputs/escenario_base/img/).
    img_dir = output_dir / f"escenario_{escenario}" / "img"
    img_anillos = img_dir / "topologia_anillos.png"
    img_a2 = img_dir / "topologia_detalle_A2.png"

    # PDF.
    pdf_path = out_oferta / f"oferta_tecnica_TAREA5_{escenario}.pdf"
    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title=f"Oferta técnica TAREA 5 — {escenario}",
        author="Proyecto ABAST",
    )

    styles = _styles()
    eq_df = scenarios_data[escenario]["equipment"]
    via_df = scenarios_data[escenario]["viability"]
    ord_df = scenarios_data[escenario]["deployment"]

    flowables: list = []
    flowables += _block_cover(styles, escenario)
    flowables += _block_1_traffic(styles, scenarios_data, chart_paths["bw"])
    flowables += _block_2_equipment(styles, eq_df, chart_paths["capex"])
    flowables += _block_3_decisions(styles, decisiones_yaml)
    flowables += _block_4_geomarketing(styles, via_df, ord_df)
    flowables += _block_5_findings(styles, eq_df, img_anillos, img_a2)

    doc.build(flowables, onFirstPage=_footer, onLaterPages=_footer)
    logger.info("Oferta técnica generada: %s", pdf_path)
    return pdf_path


def _shallow_merge(base: dict, override: dict) -> dict:
    """Merge de un nivel: base ⊕ override; para mostrar valores efectivos."""
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _shallow_merge(out[k], v)
        else:
            out[k] = v
    return out


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#7f8c8d"))
    canvas.drawString(
        2 * cm, 1.2 * cm,
        "Proyecto ABAST — Oferta técnica TAREA 5 · "
        "Master Telecomunicaciones La Salle URL",
    )
    canvas.drawRightString(
        A4[0] - 2 * cm, 1.2 * cm,
        f"Página {doc.page}",
    )
    canvas.restoreState()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Genera el PDF de oferta técnica TAREA 5.",
    )
    p.add_argument(
        "--escenario", default="base", choices=ESCENARIOS,
        help="Escenario defendido (default: base).",
    )
    p.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help="Ruta base de outputs/.",
    )
    p.add_argument(
        "--data-dir", type=Path, default=DEFAULT_DATA_DIR,
        help="Ruta a data/.",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    pdf = generate_oferta_tecnica_pdf(
        args.escenario, args.output_dir, args.data_dir,
    )
    print(f"OK -> {pdf}")

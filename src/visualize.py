"""visualize.py — gráficas y diagramas para la oferta técnica y económica.

Cubre la **parte topológica** del prompt 09 (entrega del 26/05). Las
gráficas financieras (`plot_capex_by_year`, `plot_revenue_vs_costs`,
`plot_cash_flow`, `plot_scenario_comparison`, `plot_traffic_heatmap`)
quedan pendientes hasta los prompts 05–08.

Las imágenes se generan con:
    - PNG 300dpi + SVG en paralelo
    - Layout MANUAL (flor + curvas suaves para troncales) — sin spring_layout
    - Etiquetas con bbox blanco semi-transparente para evitar overlap

Funciones públicas:
    draw_rings_only(g, output_path) -> (png, svg)
    draw_ring_detail(g, ring_id, output_path) -> (png, svg)
    draw_ring_tree(g, ring_id, output_path) -> (png, svg)
    generate_diagrams(graph, df, output_dir) -> list[Path]
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Backend sin GUI; no requiere Tk en Windows.

import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.topology import (  # noqa: E402
    EDGE_ACCESS,
    EDGE_RING_AGG,
    EDGE_RING_TRO,
    ROOT_NODE,
    resolve_aggregation_ring,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Paleta corporativa
# ---------------------------------------------------------------------------

_COLOR_ACCESS = "#76b39d"
_COLOR_AGGREGATION = "#1a5276"
_COLOR_TRONCAL = "#c0392b"
_COLOR_A900 = "#d35400"
_COLOR_EDGE_ACCESS = "#bdc3c7"
_COLOR_EDGE_AGG = "#5d6d7e"
_COLOR_TEXT = "#1c2833"

# Un color distinto por anillo troncal — para distinguir las 3 elipses
# cuando se solapan por A900.
_COLOR_T_RINGS = {
    "T1": "#c0392b",  # carmín
    "T2": "#2874a6",  # azul oscuro
    "T3": "#1e8449",  # verde oscuro
}


# ---------------------------------------------------------------------------
# Orden de los pétalos: A1..A11 en sentido horario desde arriba.
# Orden numérico → las etiquetas están donde el ojo las espera.
# ---------------------------------------------------------------------------

_PETAL_ORDER: tuple[str, ...] = (
    "A1", "A2", "A3", "A4", "A5", "A6",
    "A7", "A8", "A9", "A10", "A11",
)
assert len(_PETAL_ORDER) == 11

_R_PETAL_CENTER = 6.5
_R_CLUSTER = 1.6
_R_PETAL_LABEL = _R_PETAL_CENTER + _R_CLUSTER + 0.9


# ---------------------------------------------------------------------------
# Helpers de I/O
# ---------------------------------------------------------------------------

def _save_dual(fig: plt.Figure, output_path: Path) -> tuple[Path, Path]:
    """Guarda PNG (300dpi) y SVG. Devuelve (png_path, svg_path)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    png_path = output_path.with_suffix(".png")
    svg_path = output_path.with_suffix(".svg")
    fig.savefig(png_path, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(svg_path, bbox_inches="tight", facecolor="white")
    return png_path, svg_path


# ---------------------------------------------------------------------------
# Curva suave (Catmull-Rom) para los anillos troncales
# ---------------------------------------------------------------------------

def _catmull_rom_closed(
    points: list[tuple[float, float]],
    tension: float = 0.5,
    samples_per_seg: int = 60,
) -> np.ndarray:
    """Curva cerrada suave que pasa por todos los `points` (orden cíclico).

    Implementación pura numpy/python (sin scipy). Usa interpolación
    Hermite con tangentes Catmull-Rom.
    """
    pts = np.array(points, dtype=float)
    n = len(pts)
    if n < 3:
        return np.vstack([pts, pts[:1]])

    out: list[np.ndarray] = []
    for i in range(n):
        p0 = pts[(i - 1) % n]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n]
        m1 = (p2 - p0) * tension
        m2 = (p3 - p1) * tension
        t = np.linspace(0.0, 1.0, samples_per_seg, endpoint=False)
        h00 = 2 * t**3 - 3 * t**2 + 1
        h10 = t**3 - 2 * t**2 + t
        h01 = -2 * t**3 + 3 * t**2
        h11 = t**3 - t**2
        x = h00 * p1[0] + h10 * m1[0] + h01 * p2[0] + h11 * m2[0]
        y = h00 * p1[1] + h10 * m1[1] + h01 * p2[1] + h11 * m2[1]
        out.append(np.column_stack([x, y]))
    curve = np.vstack(out)
    curve = np.vstack([curve, curve[:1]])  # cerrar
    return curve


# ---------------------------------------------------------------------------
# Layout en flor reordenado por lóbulos T_i
# ---------------------------------------------------------------------------

def _layout_petals(g: nx.DiGraph) -> dict[str, tuple[float, float]]:
    """A900 al centro, 11 pétalos en orden _PETAL_ORDER.

    Dentro de cada cluster: el gateway (nodo con anillo troncal) se
    coloca en el lado interno (mirando hacia A900), de forma que las
    curvas de los anillos T_i pasen lo más limpiamente posible.
    """
    pos: dict[str, tuple[float, float]] = {ROOT_NODE: (0.0, 0.0)}
    for i, ring in enumerate(_PETAL_ORDER):
        angle = 2 * math.pi * i / len(_PETAL_ORDER) - math.pi / 2
        cx = _R_PETAL_CENTER * math.cos(angle)
        cy = _R_PETAL_CENTER * math.sin(angle)

        members = sorted(
            (n for n, d in g.nodes(data=True)
             if ring in d["anillos_agregacion"] and n != ROOT_NODE),
            key=lambda n: g.nodes[n]["codigo"],
        )
        if not members:
            continue

        # Identificar gateway (el que está en algún anillo troncal).
        gateway = next(
            (m for m in members if g.nodes[m]["anillos_troncal"]),
            None,
        )

        # Ángulo "interno" (apuntando hacia A900) en este pétalo.
        inner_angle = math.atan2(-cy, -cx)

        if gateway is not None:
            pos[gateway] = (
                cx + _R_CLUSTER * math.cos(inner_angle),
                cy + _R_CLUSTER * math.sin(inner_angle),
            )
            others = [m for m in members if m != gateway]
            n_o = len(others)
            for j, m in enumerate(others):
                # Distribuir los demás en el resto del círculo (excluido
                # el slot del gateway).
                t = (j + 1) / (n_o + 1)
                sub_angle = inner_angle + 2 * math.pi * t
                pos[m] = (
                    cx + _R_CLUSTER * math.cos(sub_angle),
                    cy + _R_CLUSTER * math.sin(sub_angle),
                )
        else:
            n_m = len(members)
            for j, m in enumerate(members):
                sub_angle = inner_angle + 2 * math.pi * j / n_m
                pos[m] = (
                    cx + _R_CLUSTER * math.cos(sub_angle),
                    cy + _R_CLUSTER * math.sin(sub_angle),
                )
    return pos


def _petal_label_pos(i: int) -> tuple[float, float]:
    angle = 2 * math.pi * i / len(_PETAL_ORDER) - math.pi / 2
    return (_R_PETAL_LABEL * math.cos(angle), _R_PETAL_LABEL * math.sin(angle))


# ---------------------------------------------------------------------------
# draw_rings_only — vista global con A900 + 11 pétalos + 3 elipses T_i
# ---------------------------------------------------------------------------

def draw_rings_only(g: nx.DiGraph, output_path: Path) -> tuple[Path, Path]:
    """Vista global de la topología (backbone): A900 al centro, 11 anillos
    de agregación como pétalos, 3 anillos troncales como elipses suaves."""
    pos = _layout_petals(g)
    backbone = [n for n, d in g.nodes(data=True) if d["tier"] != "acceso"]
    sub = g.subgraph(backbone)

    fig, ax = plt.subplots(figsize=(18, 18))

    # ---- Aristas internas de cada anillo de agregación (pequeños polígonos) ----
    agg_edges = [
        (u, v) for u, v, d in sub.edges(data=True)
        if d.get("tipo") == EDGE_RING_AGG
    ]
    nx.draw_networkx_edges(
        sub, pos, edgelist=agg_edges, edge_color=_COLOR_EDGE_AGG,
        width=1.3, arrows=False, ax=ax, alpha=0.85,
    )

    # ---- Curvas suaves para las 3 elipses troncales ----
    for ring in ("T1", "T2", "T3"):
        members = [
            n for n, d in g.nodes(data=True)
            if ring in d["anillos_troncal"]
        ]
        if ROOT_NODE not in members:
            continue
        gateways = [m for m in members if m != ROOT_NODE]
        # Ordenar gateways angularmente para obtener una curva limpia.
        gateways_sorted = sorted(
            gateways,
            key=lambda m: math.atan2(pos[m][1], pos[m][0]),
        )
        ring_pts = [pos[ROOT_NODE]] + [pos[m] for m in gateways_sorted]
        curve = _catmull_rom_closed(ring_pts, tension=0.45)
        color = _COLOR_T_RINGS[ring]
        ax.plot(
            curve[:, 0], curve[:, 1],
            color=color, linewidth=3.2, alpha=0.85, zorder=2,
            solid_capstyle="round",
        )
        # Etiqueta T_i fuera del centroide del lóbulo.
        gw_pts = np.array([pos[m] for m in gateways])
        cx, cy = gw_pts.mean(axis=0)
        norm = math.hypot(cx, cy) or 1.0
        scale = 1.35
        lx, ly = cx * scale, cy * scale
        ax.text(
            lx, ly, ring,
            fontsize=22, fontweight="bold", color=color,
            ha="center", va="center",
            bbox=dict(
                facecolor="white", edgecolor=color, linewidth=2.0,
                boxstyle="round,pad=0.45", alpha=0.95,
            ),
            zorder=10,
        )

    # ---- Nodos ----
    agg_nodes = [n for n in sub.nodes() if g.nodes[n]["tier"] == "agregacion"]
    tro_nodes = [n for n in sub.nodes()
                 if g.nodes[n]["tier"] == "troncal" and n != ROOT_NODE]
    nx.draw_networkx_nodes(
        sub, pos, nodelist=agg_nodes, node_color=_COLOR_AGGREGATION,
        node_size=240, edgecolors="black", linewidths=0.5, ax=ax, alpha=0.9,
    )
    nx.draw_networkx_nodes(
        sub, pos, nodelist=tro_nodes, node_color=_COLOR_TRONCAL,
        node_size=620, edgecolors="black", linewidths=0.8, ax=ax, alpha=0.95,
    )
    nx.draw_networkx_nodes(
        sub, pos, nodelist=[ROOT_NODE], node_color=_COLOR_A900,
        node_size=1300, edgecolors="black", linewidths=1.5, ax=ax,
    )

    # ---- Etiquetas A_i sobre cada cluster ----
    for i, ring in enumerate(_PETAL_ORDER):
        lx, ly = _petal_label_pos(i)
        ax.text(
            lx, ly, ring,
            fontsize=14, fontweight="bold", color=_COLOR_AGGREGATION,
            ha="center", va="center",
            bbox=dict(
                facecolor="white", edgecolor=_COLOR_AGGREGATION, linewidth=1.4,
                boxstyle="round,pad=0.32", alpha=0.95,
            ),
            zorder=9,
        )

    # ---- Etiquetas de gateways troncales (códigos A891..A899) ----
    gw_labels = {n: n for n in tro_nodes}
    nx.draw_networkx_labels(
        sub, pos, labels=gw_labels, font_size=10, font_weight="bold",
        font_color="white", ax=ax,
    )

    # ---- Etiqueta A900 (datacenter) ----
    ax.text(
        0, 0, "A900\nDC",
        fontsize=12, fontweight="bold", color="white",
        ha="center", va="center", zorder=11,
    )

    # ---- Leyenda ----
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", label="A900 (Datacenter)",
                   markerfacecolor=_COLOR_A900, markeredgecolor="black",
                   markersize=18, markeredgewidth=1.2),
        plt.Line2D([0], [0], marker="o", color="w", label="Troncal (gateway)",
                   markerfacecolor=_COLOR_TRONCAL, markeredgecolor="black",
                   markersize=14),
        plt.Line2D([0], [0], marker="o", color="w", label="Agregación",
                   markerfacecolor=_COLOR_AGGREGATION, markeredgecolor="black",
                   markersize=10),
        plt.Line2D([0], [0], color=_COLOR_T_RINGS["T1"], lw=3.2, label="Anillo T1"),
        plt.Line2D([0], [0], color=_COLOR_T_RINGS["T2"], lw=3.2, label="Anillo T2"),
        plt.Line2D([0], [0], color=_COLOR_T_RINGS["T3"], lw=3.2, label="Anillo T3"),
        plt.Line2D([0], [0], color=_COLOR_EDGE_AGG, lw=1.3, label="Anillo agregación"),
    ]
    ax.legend(
        handles=handles, loc="upper left", bbox_to_anchor=(1.0, 1.0),
        frameon=False, fontsize=12,
    )

    ax.set_title(
        "Topología ABAST — Backbone: 3 anillos troncales + 11 anillos de agregación",
        fontsize=17, color=_COLOR_TEXT, pad=24, fontweight="bold",
    )
    ax.set_aspect("equal")
    ax.set_xlim(-12, 12)
    ax.set_ylim(-12, 12)
    ax.axis("off")
    fig.tight_layout()
    paths = _save_dual(fig, output_path)
    plt.close(fig)
    logger.info("draw_rings_only → %s | %s", *paths)
    return paths


# ---------------------------------------------------------------------------
# draw_ring_detail — anillo concreto + accesos en abanico radial
# ---------------------------------------------------------------------------

def _ring_detail_layout(
    g: nx.DiGraph, ring_id: str,
) -> tuple[dict[str, tuple[float, float]], list[str], list[str]]:
    """Devuelve (pos, ring_members, access_drawn).

    Los miembros del anillo se colocan en un círculo central de radio R.
    Cada acceso "directo" (cuyo padre es un miembro del anillo) cuelga en
    un abanico radial outward desde su miembro padre. Los accesos
    indirectos (que cuelgan de otro acceso que cuelga de un miembro)
    se anidan más lejos en el mismo abanico.
    """
    members = sorted(
        (n for n, d in g.nodes(data=True) if ring_id in d["anillos_agregacion"]),
        key=lambda n: g.nodes[n]["codigo"],
    )
    n_m = max(len(members), 1)
    R = 4.0
    pos: dict[str, tuple[float, float]] = {}
    for i, m in enumerate(members):
        angle = 2 * math.pi * i / n_m - math.pi / 2
        pos[m] = (R * math.cos(angle), R * math.sin(angle))

    # Para cada acceso del anillo, encontrar el miembro del anillo al que
    # llega caminando por la cadena de acceso.
    access_to_member: dict[str, str] = {}
    for n, d in g.nodes(data=True):
        if d["tier"] != "acceso":
            continue
        if ring_id not in resolve_aggregation_ring(g, n):
            continue
        cur = n
        for _ in range(20):
            successors = [
                v for _, v, dd in g.out_edges(cur, data=True)
                if dd.get("tipo") == EDGE_ACCESS
            ]
            if not successors:
                break
            nxt = successors[0]
            if nxt in members:
                access_to_member[n] = nxt
                break
            cur = nxt

    by_member: dict[str, list[str]] = {m: [] for m in members}
    for a, m in access_to_member.items():
        by_member[m].append(a)

    half_slice = math.pi / n_m * 0.92
    fan_inner = 0.9
    layer_step = 0.55

    for i, m in enumerate(members):
        children = sorted(by_member[m], key=lambda n: g.nodes[n]["codigo"])
        n_c = len(children)
        if n_c == 0:
            continue
        ring_angle = 2 * math.pi * i / n_m - math.pi / 2

        per_row = max(8, min(22, n_c // 6 + 4))
        n_rows = math.ceil(n_c / per_row)

        for j, c in enumerate(children):
            row = j // per_row
            col = j % per_row
            in_row = min(per_row, n_c - row * per_row)
            t = 0.5 if in_row == 1 else col / max(in_row - 1, 1)
            angle = ring_angle - half_slice + 2 * half_slice * t
            r = R + fan_inner + (row + 0.5) * layer_step
            pos[c] = (r * math.cos(angle), r * math.sin(angle))

    drawn_access = list(access_to_member.keys())
    return pos, members, drawn_access


def draw_ring_detail(
    g: nx.DiGraph, ring_id: str, output_path: Path,
    show_access: bool = True,
) -> tuple[Path, Path]:
    """Vista de detalle de un anillo de agregación.

    Args:
        show_access: si False, solo se dibuja el backbone del anillo (útil
            para anillos con cientos de accesos como A2).
    """
    valid_rings = {f"A{i}" for i in range(1, 12)}
    if ring_id not in valid_rings:
        raise ValueError(f"ring_id={ring_id!r} no válido. Usa A1..A11.")

    pos, members, access_nodes = _ring_detail_layout(g, ring_id)

    drawn_access = access_nodes if show_access else []
    sub_nodes = set(members) | set(drawn_access)
    sub = g.subgraph(sub_nodes)

    fig, ax = plt.subplots(figsize=(16, 16))

    # ---- Aristas ----
    if show_access:
        access_edges = [
            (u, v) for u, v, d in sub.edges(data=True)
            if d.get("tipo") == EDGE_ACCESS
        ]
        nx.draw_networkx_edges(
            sub, pos, edgelist=access_edges, edge_color=_COLOR_EDGE_ACCESS,
            width=0.7, arrows=False, ax=ax, alpha=0.65,
        )
    ring_edges = [
        (u, v) for u, v, d in sub.edges(data=True)
        if d.get("tipo") == EDGE_RING_AGG and d.get("ring") == ring_id
    ]
    nx.draw_networkx_edges(
        sub, pos, edgelist=ring_edges, edge_color=_COLOR_T_RINGS["T1"],
        width=2.8, arrows=False, ax=ax, alpha=0.9,
    )

    # ---- Nodos ----
    members_no_root = [m for m in members if m != ROOT_NODE]
    gateways = [m for m in members_no_root if g.nodes[m]["anillos_troncal"]]
    regular  = [m for m in members_no_root if not g.nodes[m]["anillos_troncal"]]

    if show_access:
        nx.draw_networkx_nodes(
            sub, pos, nodelist=drawn_access, node_color=_COLOR_ACCESS,
            node_size=28, linewidths=0.0, ax=ax, alpha=0.9,
        )
    nx.draw_networkx_nodes(
        sub, pos, nodelist=regular, node_color=_COLOR_AGGREGATION,
        node_size=540, edgecolors="black", linewidths=0.9, ax=ax,
    )
    nx.draw_networkx_nodes(
        sub, pos, nodelist=gateways, node_color=_COLOR_TRONCAL,
        node_size=820, edgecolors="black", linewidths=1.4, ax=ax,
    )
    if ROOT_NODE in members:
        nx.draw_networkx_nodes(
            sub, pos, nodelist=[ROOT_NODE], node_color=_COLOR_A900,
            node_size=1100, edgecolors="black", linewidths=1.4, ax=ax,
        )

    # ---- Etiquetas de los miembros del anillo ----
    if not show_access:
        label_pos = {m: pos[m] for m in members}
    else:
        label_pos = {m: (pos[m][0] * 0.82, pos[m][1] * 0.82) for m in members}

    # Para gateways añadir qué anillo troncal sirven (ej. "A891\n● T1")
    labels = {}
    for m in members:
        t_rings = g.nodes[m]["anillos_troncal"]
        if t_rings:
            labels[m] = f"{m}\n● {', '.join(sorted(t_rings))}"
        else:
            labels[m] = m

    nx.draw_networkx_labels(
        sub, label_pos, labels={m: labels[m] for m in regular + ([ROOT_NODE] if ROOT_NODE in members else [])},
        font_size=11, font_weight="bold",
        font_color="white" if not show_access else _COLOR_TEXT, ax=ax,
        bbox=dict(
            facecolor=_COLOR_AGGREGATION if not show_access else "white",
            edgecolor=_COLOR_AGGREGATION, linewidth=1.0,
            boxstyle="round,pad=0.25", alpha=0.92,
        ),
    )
    if gateways:
        nx.draw_networkx_labels(
            sub, label_pos, labels={m: labels[m] for m in gateways},
            font_size=10, font_weight="bold", font_color="white", ax=ax,
            bbox=dict(
                facecolor=_COLOR_TRONCAL, edgecolor="black", linewidth=1.0,
                boxstyle="round,pad=0.28", alpha=0.95,
            ),
        )

    # ---- Etiqueta del anillo en el centro ----
    ax.text(
        0, 0, ring_id,
        fontsize=36, fontweight="bold", color=_COLOR_AGGREGATION,
        ha="center", va="center", alpha=0.18,
        zorder=0,
    )

    # ---- Anotación de accesos cuando no se dibujan ----
    if not show_access and access_nodes:
        ax.text(
            0, 0, f"{len(access_nodes)} municipios de acceso\n(no representados)",
            fontsize=13, color=_COLOR_AGGREGATION, ha="center", va="center",
            alpha=0.55, zorder=1,
        )

    all_nodes_stats = set(members) | set(access_nodes)
    sedes = sum(g.nodes[n]["sedes_abast"] for n in all_nodes_stats)
    hab = sum(g.nodes[n]["hab"] for n in all_nodes_stats)
    ax.set_title(
        f"Anillo {ring_id} — {len(members)} nodos backbone, {len(access_nodes)} accesos | "
        f"sedes ABAST: {sedes:,} · habitantes: {hab:,}",
        fontsize=16, color=_COLOR_TEXT, pad=20, fontweight="bold",
    )
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    paths = _save_dual(fig, output_path)
    plt.close(fig)
    logger.info("draw_ring_detail(%s) → %s | %s", ring_id, *paths)
    return paths


# ---------------------------------------------------------------------------
# draw_ring_tree — anillo + accesos en formato ÁRBOL radial jerárquico
# ---------------------------------------------------------------------------

def _build_access_subtrees(
    g: nx.DiGraph, ring_id: str,
) -> tuple[list[str], dict[str, dict[str, list[str]]]]:
    """Construye un sub-árbol de acceso por cada miembro del anillo.

    Cada subárbol es un dict ``{nodo: [hijos_acceso]}`` rooteado en el
    miembro del anillo. Las aristas de acceso del grafo son hijo→padre,
    así que para cada nodo padre invertimos buscando sus `in_edges` de
    tipo EDGE_ACCESS — eso da los hijos directos.

    Returns:
        (members, subtrees) donde:
            members: lista ordenada de los miembros del anillo
            subtrees[m]: dict {nodo: [hijos]} con todo el árbol acceso
                colgando de `m` (incluye el propio `m` como root).
    """
    members = sorted(
        (n for n, d in g.nodes(data=True) if ring_id in d["anillos_agregacion"]),
        key=lambda n: g.nodes[n]["codigo"],
    )

    # Pre-computar hijos directos (acceso) de cada nodo a partir de in_edges.
    children_of: dict[str, list[str]] = {}
    for n in g.nodes():
        kids = [
            u for u, _, d in g.in_edges(n, data=True)
            if d.get("tipo") == EDGE_ACCESS and g.nodes[u]["tier"] == "acceso"
        ]
        children_of[n] = sorted(kids, key=lambda x: g.nodes[x]["codigo"])

    subtrees: dict[str, dict[str, list[str]]] = {}
    for m in members:
        tree: dict[str, list[str]] = {}
        stack = [m]
        while stack:
            cur = stack.pop()
            kids = children_of.get(cur, [])
            tree[cur] = kids
            stack.extend(kids)
        subtrees[m] = tree
    return members, subtrees


def _radial_tree_layout(
    members: list[str],
    subtrees: dict[str, dict[str, list[str]]],
    r_ring: float = 4.0,
    r_step: float = 1.4,
    slice_fill: float = 0.95,
) -> tuple[dict[str, tuple[float, float]], int]:
    """Layout radial: anillo en el centro, cada subárbol en su slice angular.

    Cada hijo recibe una sub-slice de tamaño proporcional a su número de
    hojas, lo que evita que ramas pobladas se solapen con ramas escasas.
    El radio crece linealmente con la profundidad del nodo en el árbol.

    Args:
        slice_fill: fracción del slice angular que se rellena (deja un
            "respiradero" entre subárboles vecinos).

    Returns:
        (pos, max_depth) donde pos es {nodo: (x, y)}.
    """
    n_m = len(members)
    pos: dict[str, tuple[float, float]] = {}

    # Conteo de hojas por nodo (memoizado).
    leaves_cache: dict[tuple[str, str], int] = {}

    def n_leaves(tree: dict[str, list[str]], node: str) -> int:
        key = (id(tree).__str__(), node)
        if key in leaves_cache:
            return leaves_cache[key]
        kids = tree.get(node, [])
        v = 1 if not kids else sum(n_leaves(tree, c) for c in kids)
        leaves_cache[key] = v
        return v

    # Pesos por miembro = log(leaves+2) → comprime extremos pero respeta
    # la jerarquía de tamaños. En A2: A800≈6.5, A801≈3.4, A802≈4.5, otros≈0.7-1.1.
    leaf_count = {m: n_leaves(subtrees[m], m) for m in members}
    weights = {m: math.log(leaf_count[m] + 2) for m in members}
    total_w = sum(weights.values()) or 1.0

    # ---- Posición no equidistante de los miembros del anillo ----
    # Cada miembro recibe un "sector angular" proporcional a su peso, y
    # se sitúa en el centro de su sector. Empezamos por la mitad del
    # primer sector, contando desde el ángulo base (-π/2 = sur).
    base_angle = -math.pi / 2
    member_angle: dict[str, float] = {}
    sector_half: dict[str, float] = {}
    cum = 0.0
    for m in members:
        sector_w = 2 * math.pi * weights[m] / total_w
        member_angle[m] = base_angle + 2 * math.pi * (cum + weights[m] / total_w / 2)
        sector_half[m] = sector_w / 2
        pos[m] = (r_ring * math.cos(member_angle[m]),
                  r_ring * math.sin(member_angle[m]))
        cum += weights[m] / total_w

    # Slice = sector completo (con un pequeño margen) → el subárbol llena
    # exactamente el espacio asignado en el anillo, sin solapar al vecino.
    slice_by_member = {m: 2 * sector_half[m] * slice_fill for m in members}

    max_depth = 0

    def place(
        tree: dict[str, list[str]],
        node: str,
        center_a: float,
        slice_w: float,
        depth: int,
    ) -> None:
        nonlocal max_depth
        max_depth = max(max_depth, depth)
        kids = tree.get(node, [])
        if not kids:
            return
        weights = [n_leaves(tree, c) for c in kids]
        total = sum(weights) or 1
        cur = center_a - slice_w / 2
        r = r_ring + r_step * depth
        for c, w in zip(kids, weights):
            child_w = slice_w * w / total
            child_a = cur + child_w / 2
            pos[c] = (r * math.cos(child_a), r * math.sin(child_a))
            place(tree, c, child_a, child_w * slice_fill, depth + 1)
            cur += child_w

    for m in members:
        place(subtrees[m], m, member_angle[m], slice_by_member[m], 1)

    return pos, max_depth


def draw_ring_tree(
    g: nx.DiGraph,
    ring_id: str,
    output_path: Path,
) -> tuple[Path, Path]:
    """Vista del anillo + accesos en formato ÁRBOL radial jerárquico.

    Cada miembro del anillo es la raíz de un subárbol cuyas ramas se
    despliegan radialmente hacia fuera. Los hijos directos del miembro
    quedan en el primer "anillo" exterior, los nietos en el segundo, etc.
    La conexión visual padre↔hijo se conserva exactamente — al contrario
    que el `draw_ring_detail` tradicional, donde los accesos se aplastan
    en un abanico ignorando la jerarquía multi-hop.

    Pensado especialmente para A2 (~782 accesos en cadenas profundas).
    """
    valid_rings = {f"A{i}" for i in range(1, 12)}
    if ring_id not in valid_rings:
        raise ValueError(f"ring_id={ring_id!r} no válido. Usa A1..A11.")

    members, subtrees = _build_access_subtrees(g, ring_id)
    if not members:
        raise ValueError(f"Anillo {ring_id} sin miembros en el grafo.")

    n_access = sum(
        len([n for n in tree if n != root])
        for root, tree in subtrees.items()
    )

    # Escalar radios según el número de accesos para que A2 (~782) y A11
    # (~muy pocos) se vean ambos legibles.
    r_ring = 4.0
    r_step = max(0.7, min(1.6, 80.0 / max(n_access, 1) + 0.6))

    pos, max_depth = _radial_tree_layout(members, subtrees, r_ring=r_ring, r_step=r_step)

    # Subgrafo: miembros + todos los accesos colgando de ellos.
    all_access = {n for tree in subtrees.values() for n in tree if n not in members}
    sub_nodes = set(members) | all_access
    sub = g.subgraph(sub_nodes)

    fig, ax = plt.subplots(figsize=(18, 18))

    # ---- Aristas de acceso (hijo→padre) ----
    access_edges = [
        (u, v) for u, v, d in sub.edges(data=True)
        if d.get("tipo") == EDGE_ACCESS
    ]
    nx.draw_networkx_edges(
        sub, pos, edgelist=access_edges, edge_color=_COLOR_EDGE_ACCESS,
        width=0.6, arrows=False, ax=ax, alpha=0.7,
    )

    # ---- Aristas del anillo (rojo, encima) ----
    ring_edges = [
        (u, v) for u, v, d in sub.edges(data=True)
        if d.get("tipo") == EDGE_RING_AGG and d.get("ring") == ring_id
    ]
    nx.draw_networkx_edges(
        sub, pos, edgelist=ring_edges, edge_color=_COLOR_T_RINGS["T1"],
        width=2.6, arrows=False, ax=ax, alpha=0.9,
    )

    # ---- Nodos ----
    members_no_root = [m for m in members if m != ROOT_NODE]
    gateways = [m for m in members_no_root if g.nodes[m]["anillos_troncal"]]
    regular = [m for m in members_no_root if not g.nodes[m]["anillos_troncal"]]

    # Tamaño de los nodos de acceso decreciente con la profundidad.
    nx.draw_networkx_nodes(
        sub, pos, nodelist=sorted(all_access),
        node_color=_COLOR_ACCESS, node_size=20,
        linewidths=0.0, ax=ax, alpha=0.9,
    )
    nx.draw_networkx_nodes(
        sub, pos, nodelist=regular, node_color=_COLOR_AGGREGATION,
        node_size=520, edgecolors="black", linewidths=0.9, ax=ax,
    )
    nx.draw_networkx_nodes(
        sub, pos, nodelist=gateways, node_color=_COLOR_TRONCAL,
        node_size=820, edgecolors="black", linewidths=1.4, ax=ax,
    )
    if ROOT_NODE in members:
        nx.draw_networkx_nodes(
            sub, pos, nodelist=[ROOT_NODE], node_color=_COLOR_A900,
            node_size=1100, edgecolors="black", linewidths=1.4, ax=ax,
        )

    # ---- Etiquetas: sólo miembros del anillo (etiquetar 782 accesos sería ilegible) ----
    labels = {}
    for m in members:
        t_rings = g.nodes[m]["anillos_troncal"]
        labels[m] = f"{m}\n● {', '.join(sorted(t_rings))}" if t_rings else m

    nx.draw_networkx_labels(
        sub, pos,
        labels={m: labels[m] for m in regular + ([ROOT_NODE] if ROOT_NODE in members else [])},
        font_size=10, font_weight="bold", font_color=_COLOR_TEXT, ax=ax,
        bbox=dict(
            facecolor="white", edgecolor=_COLOR_AGGREGATION, linewidth=1.0,
            boxstyle="round,pad=0.25", alpha=0.95,
        ),
    )
    if gateways:
        nx.draw_networkx_labels(
            sub, pos, labels={m: labels[m] for m in gateways},
            font_size=10, font_weight="bold", font_color="white", ax=ax,
            bbox=dict(
                facecolor=_COLOR_TRONCAL, edgecolor="black", linewidth=1.0,
                boxstyle="round,pad=0.28", alpha=0.95,
            ),
        )

    # ---- Etiqueta gigante del anillo en el centro ----
    ax.text(
        0, 0, ring_id,
        fontsize=42, fontweight="bold", color=_COLOR_AGGREGATION,
        ha="center", va="center", alpha=0.18, zorder=0,
    )

    # ---- Leyenda ----
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", label="Gateway troncal",
                   markerfacecolor=_COLOR_TRONCAL, markeredgecolor="black",
                   markersize=14),
        plt.Line2D([0], [0], marker="o", color="w", label="Nodo agregación",
                   markerfacecolor=_COLOR_AGGREGATION, markeredgecolor="black",
                   markersize=11),
        plt.Line2D([0], [0], marker="o", color="w", label="Municipio acceso",
                   markerfacecolor=_COLOR_ACCESS, markeredgecolor="none",
                   markersize=7),
        plt.Line2D([0], [0], color=_COLOR_T_RINGS["T1"], lw=2.6, label=f"Anillo {ring_id}"),
        plt.Line2D([0], [0], color=_COLOR_EDGE_ACCESS, lw=0.8, label="Enlace acceso (hijo→padre)"),
    ]
    ax.legend(
        handles=handles, loc="upper left", bbox_to_anchor=(1.0, 1.0),
        frameon=False, fontsize=11,
    )

    sedes = sum(g.nodes[n]["sedes_abast"] for n in sub_nodes)
    hab = sum(g.nodes[n]["hab"] for n in sub_nodes)
    ax.set_title(
        f"Anillo {ring_id} — árbol de acceso jerárquico | "
        f"{len(members)} backbone + {n_access} accesos (profundidad máx {max_depth}) | "
        f"sedes ABAST: {sedes:,} · habitantes: {hab:,}",
        fontsize=14, color=_COLOR_TEXT, pad=20, fontweight="bold",
    )
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    paths = _save_dual(fig, output_path)
    plt.close(fig)
    logger.info("draw_ring_tree(%s) → %s | %s", ring_id, *paths)
    return paths


# ---------------------------------------------------------------------------
# Entry point usado por main.py
# ---------------------------------------------------------------------------

def generate_diagrams(
    graph: nx.DiGraph,
    df: pd.DataFrame,
    output_dir: Path,
) -> list[Path]:
    """Genera la batería topológica para la oferta técnica.

    Salida (en `output_dir/img/`):
        - topologia_anillos.{png,svg}        — vista global backbone
        - topologia_detalle_A2.{png,svg}     — espina dorsal (~782 accesos, árbol radial)
        - topologia_detalle_A6.{png,svg}     — anillo mediano
        - topologia_detalle_A11.{png,svg}    — anillo más pequeño (4 nodos)
    """
    output_dir = Path(output_dir)
    img_dir = output_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    written.extend(draw_rings_only(graph, img_dir / "topologia_anillos"))
    written.extend(draw_ring_tree(graph, "A2",  img_dir / "topologia_detalle_A2"))
    written.extend(draw_ring_detail(graph, "A6",  img_dir / "topologia_detalle_A6"))
    written.extend(draw_ring_detail(graph, "A11", img_dir / "topologia_detalle_A11"))
    return written

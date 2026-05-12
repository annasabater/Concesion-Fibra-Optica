"""topology.py — grafo NetworkX de la red ABAST con A900 como root.

Construye un grafo dirigido (`nx.DiGraph`) que representa las 3 capas
(troncal, agregación, acceso). La convención de aristas del árbol de
acceso es **hijo → padre** (apuntando hacia A900), lo que facilita el
cálculo de tráfico acumulado por BFS desde las hojas.

Funciones públicas:
    build_graph(df) -> nx.DiGraph
    get_root(g) -> str
    get_downstream_nodes(g, node) -> set[str]
    resolve_aggregation_ring(g, node) -> set[str]
    stats_by_ring(g) -> pd.DataFrame
    traffic_by_ring(g, df_traffic) -> pd.DataFrame
    draw_rings_only(g, output_path) -> None
    draw_full_topology(g, output_path) -> None
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Backend sin GUI; no requiere Tk en Windows.

import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import pandas as pd  # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

ROOT_NODE = "A900"

EDGE_ACCESS = "acceso"
EDGE_RING_AGG = "anillo_agregacion"
EDGE_RING_TRO = "anillo_troncal"

_AGG_RINGS: tuple[str, ...] = tuple(f"A{i}" for i in range(1, 12))
_TRO_RINGS: tuple[str, ...] = ("T1", "T2", "T3")


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------

def build_graph(df: pd.DataFrame) -> nx.DiGraph:
    """Construye el grafo dirigido de la red completa.

    Convención de aristas del árbol de acceso: hijo → padre (apuntando
    hacia A900). Para los anillos (agregación y troncal) se añaden
    aristas cíclicas de tipo `EDGE_RING_AGG` / `EDGE_RING_TRO` que NO
    contribuyen al árbol jerárquico — son sólo para análisis topológico
    y visualización de redundancia.

    Atributos de nodo:
        codigo (int), tier ('acceso'|'agregacion'|'troncal'),
        hab (int), sedes_abast (int), num_operadores (int),
        anillos_agregacion (set[str]), anillos_troncal (set[str]),
        km (float)  — km al destino_acceso, sólo informativo.

    Atributos de arista:
        tipo (str), km (float), ring (str | None).

    Args:
        df: DataFrame devuelto por `load.load_topology` (900 filas).

    Returns:
        Grafo `nx.DiGraph` con 900 nodos y aristas de los 3 tipos.
    """
    g = nx.DiGraph()

    # ---- nodos ----
    for _, row in df.iterrows():
        node_id = row["municipio"]
        anillos_agg = (
            set(row["anillo_agregacion"].split(","))
            if pd.notna(row["anillo_agregacion"]) else set()
        )
        anillos_tro = (
            set(row["anillo_troncal"].split(","))
            if pd.notna(row["anillo_troncal"]) else set()
        )
        g.add_node(
            node_id,
            codigo=int(row["codigo"]),
            tier=str(row["tier"]),
            hab=int(row["hab"]),
            sedes_abast=int(row["sedes_abast"]),
            num_operadores=int(row["num_operadores"]),
            anillos_agregacion=anillos_agg,
            anillos_troncal=anillos_tro,
            km=float(row["km"]),
        )

    # ---- aristas de acceso (hijo → padre) ----
    for _, row in df.iterrows():
        destino = row["destino_acceso"]
        origen = row["municipio"]
        if pd.isna(destino) or destino is None or destino == origen:
            continue
        if destino not in g:
            logger.warning(
                "destino_acceso=%s del municipio %s no está en el grafo; skip.",
                destino, origen,
            )
            continue
        g.add_edge(origen, destino, tipo=EDGE_ACCESS, km=float(row["km"]))

    # ---- aristas de los anillos de agregación (cíclicas, ordenadas por código) ----
    for ring in _AGG_RINGS:
        members = sorted(
            (n for n, d in g.nodes(data=True) if ring in d["anillos_agregacion"]),
            key=lambda n: g.nodes[n]["codigo"],
        )
        for i, n in enumerate(members):
            nxt = members[(i + 1) % len(members)]
            if n != nxt:
                g.add_edge(n, nxt, tipo=EDGE_RING_AGG, ring=ring, km=0.0)

    # ---- aristas de los anillos troncales (cíclicas) ----
    for ring in _TRO_RINGS:
        members = sorted(
            (n for n, d in g.nodes(data=True) if ring in d["anillos_troncal"]),
            key=lambda n: g.nodes[n]["codigo"],
        )
        for i, n in enumerate(members):
            nxt = members[(i + 1) % len(members)]
            if n != nxt:
                g.add_edge(n, nxt, tipo=EDGE_RING_TRO, ring=ring, km=0.0)

    logger.info(
        "build_graph: %d nodos, %d aristas (acceso=%d, anillo_agg=%d, anillo_tro=%d)",
        g.number_of_nodes(),
        g.number_of_edges(),
        sum(1 for _, _, d in g.edges(data=True) if d.get("tipo") == EDGE_ACCESS),
        sum(1 for _, _, d in g.edges(data=True) if d.get("tipo") == EDGE_RING_AGG),
        sum(1 for _, _, d in g.edges(data=True) if d.get("tipo") == EDGE_RING_TRO),
    )
    return g


# ---------------------------------------------------------------------------
# Helpers de navegación
# ---------------------------------------------------------------------------

def get_root(g: nx.DiGraph) -> str:
    """Devuelve el código del nodo raíz (A900)."""
    if ROOT_NODE not in g:
        raise ValueError(f"El grafo no contiene el nodo raíz {ROOT_NODE}.")
    return ROOT_NODE


def get_downstream_nodes(g: nx.DiGraph, node: str) -> set[str]:
    """Devuelve todos los nodos aguas abajo del dado siguiendo aristas 'acceso'.

    Como las aristas de acceso apuntan hijo → padre, los descendientes
    aguas abajo son los `predecessors` que llegan al nodo por aristas
    de tipo 'acceso' (recursivamente).

    Args:
        g: grafo.
        node: código del municipio.

    Returns:
        Set de códigos de municipios cuyos paquetes pasan por `node`.
    """
    if node not in g:
        raise ValueError(f"Nodo {node!r} no existe en el grafo.")

    downstream: set[str] = set()
    stack = [node]
    while stack:
        cur = stack.pop()
        for u, _, d in g.in_edges(cur, data=True):
            if d.get("tipo") != EDGE_ACCESS:
                continue
            if u in downstream:
                continue
            downstream.add(u)
            stack.append(u)
    return downstream


def resolve_aggregation_ring(
    g: nx.DiGraph,
    node: str,
    max_hops: int = 20,
) -> set[str]:
    """Resuelve a qué anillo(s) de agregación pertenece un municipio.

    - Si `node` ya es de tier agregación o troncal, devuelve directamente
      sus `anillos_agregacion`.
    - Si es de acceso, sigue la cadena `destino_acceso` hasta dar con un
      nodo de tier no-acceso, y devuelve sus `anillos_agregacion`.

    Args:
        g: grafo.
        node: código del municipio a resolver.
        max_hops: tope de iteraciones para detectar ciclos (default 20).

    Returns:
        Set de nombres de anillos de agregación. Vacío si no se puede
        resolver (cadena rota o ciclo).
    """
    if node not in g:
        raise ValueError(f"Nodo {node!r} no existe en el grafo.")

    if g.nodes[node]["tier"] != "acceso":
        return set(g.nodes[node]["anillos_agregacion"])

    cur = node
    seen: set[str] = set()
    for _ in range(max_hops):
        if cur in seen:
            logger.warning("Ciclo detectado al resolver anillo de %s", node)
            return set()
        seen.add(cur)
        successors = [
            v for _, v, d in g.out_edges(cur, data=True)
            if d.get("tipo") == EDGE_ACCESS
        ]
        if not successors:
            return set()
        cur = successors[0]
        if g.nodes[cur]["tier"] != "acceso":
            return set(g.nodes[cur]["anillos_agregacion"])
    logger.warning("max_hops=%d alcanzado al resolver anillo de %s", max_hops, node)
    return set()


# ---------------------------------------------------------------------------
# stats_by_ring
# ---------------------------------------------------------------------------

def stats_by_ring(g: nx.DiGraph) -> pd.DataFrame:
    """Tabla resumen por anillo (3 troncales + 11 agregación = 14 filas).

    Columnas:
        anillo, tipo, n_nodos, n_munis_cubiertos, n_sedes_abast,
        total_hab, km_existing, km_acceso_construido.

    Para anillos de agregación, `n_munis_cubiertos` cuenta a los miembros
    propios del anillo más todos los municipios de acceso que resuelven a
    él vía `resolve_aggregation_ring`. Para troncales, también cubre los
    munis de los anillos de agregación que cuelgan del troncal.

    `km_existing` queda como NaN porque el Excel no desglosa los km de
    backbone por anillo (sólo da los totales 1.000 km troncal y 2.000 km
    agregación). `km_acceso_construido` suma los km de los enlaces de
    acceso de los munis que resuelven al anillo.
    """
    # Pre-resolver anillo destino para cada nodo de acceso (evita O(n²)).
    access_to_rings: dict[str, set[str]] = {}
    for n, d in g.nodes(data=True):
        if d["tier"] == "acceso":
            access_to_rings[n] = resolve_aggregation_ring(g, n)

    rows: list[dict] = []

    # ---- 11 anillos de agregación ----
    for ring in _AGG_RINGS:
        members = {n for n, d in g.nodes(data=True) if ring in d["anillos_agregacion"]}
        access_resolving = {n for n, rings in access_to_rings.items() if ring in rings}
        cubiertos = members | access_resolving
        rows.append({
            "anillo": ring,
            "tipo": "agregacion",
            "n_nodos": len(members),
            "n_munis_cubiertos": len(cubiertos),
            "n_sedes_abast": int(sum(g.nodes[n]["sedes_abast"] for n in cubiertos)),
            "total_hab": int(sum(g.nodes[n]["hab"] for n in cubiertos)),
            "km_existing": float("nan"),
            "km_acceso_construido": float(
                sum(g.nodes[n]["km"] for n in access_resolving)
            ),
        })

    # ---- 3 anillos troncales ----
    for ring in _TRO_RINGS:
        members = {n for n, d in g.nodes(data=True) if ring in d["anillos_troncal"]}
        # Anillos de agregación que cuelgan de este troncal.
        agg_rings_under: set[str] = set()
        for n in members:
            agg_rings_under |= g.nodes[n]["anillos_agregacion"]
        # Munis cubiertos = miembros del troncal + cubiertos por sus agg rings.
        cubiertos: set[str] = set(members)
        for ar in agg_rings_under:
            cubiertos |= {n for n, d in g.nodes(data=True) if ar in d["anillos_agregacion"]}
            cubiertos |= {n for n, rings in access_to_rings.items() if ar in rings}
        rows.append({
            "anillo": ring,
            "tipo": "troncal",
            "n_nodos": len(members),
            "n_munis_cubiertos": len(cubiertos),
            "n_sedes_abast": int(sum(g.nodes[n]["sedes_abast"] for n in cubiertos)),
            "total_hab": int(sum(g.nodes[n]["hab"] for n in cubiertos)),
            "km_existing": float("nan"),
            "km_acceso_construido": float(
                sum(
                    g.nodes[n]["km"] for n in cubiertos
                    if g.nodes[n]["tier"] == "acceso"
                )
            ),
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# traffic_by_ring
# ---------------------------------------------------------------------------

def traffic_by_ring(
    g: nx.DiGraph,
    df_traffic: pd.DataFrame,
) -> pd.DataFrame:
    """Tráfico ABAST y mayorista agregado por anillo (14 filas).

    Para anillos de agregación (A1-A11): suma el tráfico de todos los
    municipios de acceso que resuelven a ese anillo.

    Para anillos troncales (T1-T3): suma el tráfico de los anillos de
    agregación cuyos gateways pertenecen a ese troncal. A1 y A2 cuelgan
    directamente de A900 (que está en los 3 troncales) y no atraviesan
    ningún segmento troncal, por lo que no se suman a T1/T2/T3.

    Args:
        g: grafo de `build_graph`.
        df_traffic: salida de `traffic.compute_traffic` con columnas
            municipio, bw_abast_mbps, bw_mayorista_mbps.

    Returns:
        DataFrame: anillo, tipo, bw_abast_gbps, bw_mayorista_gbps,
        bw_total_gbps.
    """
    # Índice municipio → tráfico
    traffic_idx = df_traffic.set_index("municipio")

    def _mbps(node: str, col: str) -> float:
        try:
            return float(traffic_idx.loc[node, col])
        except KeyError:
            return 0.0

    # Pre-resolver anillos de acceso (igual que en stats_by_ring)
    access_to_rings: dict[str, set[str]] = {}
    for n, d in g.nodes(data=True):
        if d["tier"] == "acceso":
            access_to_rings[n] = resolve_aggregation_ring(g, n)

    rows: list[dict] = []

    # ---- tráfico por anillo de agregación ----
    agg_bw: dict[str, tuple[float, float]] = {}  # ring → (abast, mayo)
    for ring in _AGG_RINGS:
        munis = {n for n, rings in access_to_rings.items() if ring in rings}
        abast = sum(_mbps(m, "bw_abast_mbps") for m in munis)
        mayo = sum(_mbps(m, "bw_mayorista_mbps") for m in munis)
        agg_bw[ring] = (abast, mayo)
        rows.append({
            "anillo": ring,
            "tipo": "agregacion",
            "bw_abast_gbps": round(abast / 1000, 2),
            "bw_mayorista_gbps": round(mayo / 1000, 2),
            "bw_total_gbps": round((abast + mayo) / 1000, 2),
        })

    # ---- tráfico por anillo troncal ----
    # Para cada troncal, sumar los anillos de agregación cuyos gateways son
    # nodos del troncal (excluyendo A900, que es el root compartido).
    for tring in _TRO_RINGS:
        tro_nodes = {
            n for n, d in g.nodes(data=True)
            if tring in d["anillos_troncal"] and n != ROOT_NODE
        }
        # Anillos de agregación que tienen gateway en este troncal.
        agg_rings_under: set[str] = set()
        for n in tro_nodes:
            agg_rings_under |= g.nodes[n]["anillos_agregacion"]

        abast = sum(agg_bw[ar][0] for ar in agg_rings_under)
        mayo = sum(agg_bw[ar][1] for ar in agg_rings_under)
        rows.append({
            "anillo": tring,
            "tipo": "troncal",
            "bw_abast_gbps": round(abast / 1000, 2),
            "bw_mayorista_gbps": round(mayo / 1000, 2),
            "bw_total_gbps": round((abast + mayo) / 1000, 2),
        })

    # Ordenar: A1..A11, T1, T2, T3
    order = {r: i for i, r in enumerate(list(_AGG_RINGS) + list(_TRO_RINGS))}
    df = pd.DataFrame(rows).sort_values(
        "anillo", key=lambda s: s.map(order)
    ).reset_index(drop=True)

    logger.info(
        "traffic_by_ring: BW total territorio = %.1f Gbps (ABAST=%.1f, Mayo=%.1f)",
        df["bw_total_gbps"].sum(),
        df["bw_abast_gbps"].sum(),
        df["bw_mayorista_gbps"].sum(),
    )
    return df


# ---------------------------------------------------------------------------
# Visualización (vistas preliminares — la versión final va en visualize.py)
# ---------------------------------------------------------------------------

def _layout_rings_only(g: nx.DiGraph) -> dict[str, tuple[float, float]]:
    """Layout manual: A900 al centro, los 11 anillos de agregación
    distribuidos radialmente en pétalos, troncales superpuestos por sus
    nodos compartidos (no requieren layout independiente)."""
    pos: dict[str, tuple[float, float]] = {ROOT_NODE: (0.0, 0.0)}

    R_AGG_CENTER = 6.0   # distancia del centro a cada cluster A_i
    R_AGG_RADIUS = 1.6   # radio del cluster de cada A_i

    for i, ring in enumerate(_AGG_RINGS):
        angle = 2 * math.pi * i / len(_AGG_RINGS) - math.pi / 2  # empieza arriba
        cx = R_AGG_CENTER * math.cos(angle)
        cy = R_AGG_CENTER * math.sin(angle)
        members = sorted(
            (n for n, d in g.nodes(data=True)
             if ring in d["anillos_agregacion"] and n != ROOT_NODE),
            key=lambda n: g.nodes[n]["codigo"],
        )
        n_m = max(len(members), 1)
        for j, m in enumerate(members):
            theta = 2 * math.pi * j / n_m + angle
            pos[m] = (cx + R_AGG_RADIUS * math.cos(theta),
                      cy + R_AGG_RADIUS * math.sin(theta))
    return pos


def draw_rings_only(g: nx.DiGraph, output_path: Path) -> None:
    """Dibuja sólo la capa troncal + agregación."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pos = _layout_rings_only(g)
    backbone = [n for n, d in g.nodes(data=True) if d["tier"] != "acceso"]
    sub = g.subgraph(backbone)

    fig, ax = plt.subplots(figsize=(14, 14))

    # Aristas: agregación primero, troncal encima.
    for tipo, color, width in [
        (EDGE_RING_AGG, "#9aa0a6", 1.2),
        (EDGE_RING_TRO, "#c0392b", 2.0),
    ]:
        edges = [(u, v) for u, v, d in sub.edges(data=True) if d.get("tipo") == tipo]
        nx.draw_networkx_edges(
            sub, pos, edgelist=edges, edge_color=color, width=width,
            arrows=False, ax=ax,
        )

    # Nodos por tier.
    agg_nodes = [n for n in sub.nodes() if g.nodes[n]["tier"] == "agregacion"]
    tro_nodes = [n for n in sub.nodes() if g.nodes[n]["tier"] == "troncal" and n != ROOT_NODE]
    nx.draw_networkx_nodes(
        sub, pos, nodelist=agg_nodes,
        node_color="#5dade2", node_size=180, edgecolors="#21618c", ax=ax,
    )
    nx.draw_networkx_nodes(
        sub, pos, nodelist=tro_nodes,
        node_color="#f5b041", node_size=420, edgecolors="#7e5109", ax=ax,
    )
    nx.draw_networkx_nodes(
        sub, pos, nodelist=[ROOT_NODE],
        node_color="#c0392b", node_size=900, edgecolors="black", ax=ax,
    )

    # Etiquetas: A900 + troncales.
    labels = {n: n for n in tro_nodes}
    labels[ROOT_NODE] = "A900\n(DC)"
    nx.draw_networkx_labels(sub, pos, labels=labels, font_size=9,
                            font_weight="bold", ax=ax)

    ax.set_title(
        "Topología ABAST — Anillos troncal (rojo) + agregación (gris) | "
        f"{len(backbone)} nodos backbone",
        fontsize=13,
    )
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("draw_rings_only: %s", output_path)


def _layout_full(g: nx.DiGraph) -> dict[str, tuple[float, float]]:
    """Layout completo: backbone + acceso colgando radialmente de su A-ring."""
    pos = _layout_rings_only(g)

    R_ACCESS_INNER = 8.0
    R_ACCESS_OUTER = 12.0

    # Pre-resolver ring para cada acceso.
    access_by_ring: dict[str, list[str]] = {r: [] for r in _AGG_RINGS}
    for n, d in g.nodes(data=True):
        if d["tier"] != "acceso":
            continue
        rings = resolve_aggregation_ring(g, n)
        if not rings:
            continue
        target = sorted(rings, key=lambda r: int(r[1:]))[0]
        if target in access_by_ring:
            access_by_ring[target].append(n)

    for i, ring in enumerate(_AGG_RINGS):
        angle = 2 * math.pi * i / len(_AGG_RINGS) - math.pi / 2
        nodes = sorted(access_by_ring[ring], key=lambda n: g.nodes[n]["codigo"])
        n_n = max(len(nodes), 1)
        # Slice angular asignado a este anillo.
        slice_half = math.pi / len(_AGG_RINGS) * 0.9  # cubre 90% del sector
        for j, m in enumerate(nodes):
            t = j / max(n_n - 1, 1)  # 0..1
            theta = angle - slice_half + 2 * slice_half * t
            r = R_ACCESS_INNER + (R_ACCESS_OUTER - R_ACCESS_INNER) * (j % 5) / 5
            pos[m] = (r * math.cos(theta), r * math.sin(theta))
    return pos


def draw_full_topology(g: nx.DiGraph, output_path: Path) -> None:
    """Dibuja la topología completa (900 municipios)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pos = _layout_full(g)

    fig, ax = plt.subplots(figsize=(20, 20))

    # Aristas de acceso primero (más claras, debajo).
    access_edges = [(u, v) for u, v, d in g.edges(data=True) if d.get("tipo") == EDGE_ACCESS]
    nx.draw_networkx_edges(
        g, pos, edgelist=access_edges, edge_color="#d5dbdb",
        width=0.4, arrows=False, ax=ax,
    )

    # Aristas de anillos.
    for tipo, color, width in [
        (EDGE_RING_AGG, "#5d6d7e", 1.0),
        (EDGE_RING_TRO, "#c0392b", 2.0),
    ]:
        edges = [(u, v) for u, v, d in g.edges(data=True) if d.get("tipo") == tipo]
        nx.draw_networkx_edges(
            g, pos, edgelist=edges, edge_color=color, width=width,
            arrows=False, ax=ax,
        )

    # Nodos por tier.
    acceso = [n for n, d in g.nodes(data=True) if d["tier"] == "acceso"]
    agreg = [n for n, d in g.nodes(data=True) if d["tier"] == "agregacion"]
    tronc = [n for n, d in g.nodes(data=True) if d["tier"] == "troncal" and n != ROOT_NODE]

    nx.draw_networkx_nodes(
        g, pos, nodelist=acceso, node_color="#aed6f1",
        node_size=8, ax=ax, linewidths=0.0,
    )
    nx.draw_networkx_nodes(
        g, pos, nodelist=agreg, node_color="#2874a6",
        node_size=80, edgecolors="black", linewidths=0.4, ax=ax,
    )
    nx.draw_networkx_nodes(
        g, pos, nodelist=tronc, node_color="#f5b041",
        node_size=300, edgecolors="black", linewidths=0.6, ax=ax,
    )
    nx.draw_networkx_nodes(
        g, pos, nodelist=[ROOT_NODE], node_color="#c0392b",
        node_size=700, edgecolors="black", linewidths=1.0, ax=ax,
    )

    labels = {n: n for n in tronc}
    labels[ROOT_NODE] = "A900\n(DC)"
    nx.draw_networkx_labels(g, pos, labels=labels, font_size=8,
                            font_weight="bold", ax=ax)

    ax.set_title(
        f"Topología ABAST — Red completa | "
        f"{g.number_of_nodes()} nodos, {g.number_of_edges()} aristas",
        fontsize=14,
    )
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    logger.info("draw_full_topology: %s", output_path)

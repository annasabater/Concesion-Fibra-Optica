"""equipment.py — tráfico acumulado y selección de equipo por nodo.

Dos pasadas:

1) **Tráfico acumulado** (`cumulative_traffic`): BFS sobre el grafo de la
   topología desde las hojas del árbol de acceso hacia A900, sumando
   tráfico. Se hace en tres fases para reflejar la jerarquía:
        a. Pasada por aristas de acceso (hijo → padre) en orden topológico.
        b. Cada anillo de agregación reenvía su total al *gateway* (nodo
           del anillo que también está en un anillo troncal).
        c. Cada anillo troncal reenvía su total a A900.

2) **Selección de equipo** (`select_equipment`): elige por nodo el equipo
   apropiado (cliente, agregación 10/20/40 puertos, MPLS troncal, óptico
   40 lambdas) según los umbrales de `decisiones['equipos']` y el tráfico
   acumulado, y calcula el CAPEX.

API pública (ver `src/prompts/04_equipment.md`):
    cumulative_traffic(graph, df_traffic) -> DataFrame
    select_equipment(df_cumulative, decisiones, parametros) -> DataFrame
    total_capex_equipos(df_equipment) -> dict
    assign_equipment(graph, traffic, decisiones, parametros) -> DataFrame
"""

from __future__ import annotations

import logging
import math

import networkx as nx
import pandas as pd

from src.topology import (
    EDGE_ACCESS,
    ROOT_NODE,
    _AGG_RINGS,
    _TRO_RINGS,
)

logger = logging.getLogger(__name__)


# Capacidades nominales (Mbps) para escalar el equipo si el BW excede.
_CAPACIDAD_AGREG_10P_MBPS = 10_000   # 10 puertos × 1 Gbps
_CAPACIDAD_AGREG_20P_MBPS = 20_000
_CAPACIDAD_AGREG_40P_MBPS = 40_000
_CAPACIDAD_MPLS_MBPS = 100_000       # MPLS troncal típico ~100 Gbps
_CAPACIDAD_OPTICO_40L_MBPS = 400_000  # 40 λ × 10 Gbps


# ---------------------------------------------------------------------------
# cumulative_traffic
# ---------------------------------------------------------------------------

def cumulative_traffic(
    graph: nx.DiGraph,
    df_traffic_per_muni: pd.DataFrame,
) -> pd.DataFrame:
    """Tráfico acumulado en cada nodo del grafo.

    El BW acumulado en A900 debe igualar el BW total del territorio
    (suma de bw_total_mbps de todos los municipios).

    Args:
        graph: grafo de `topology.build_graph`.
        df_traffic_per_muni: salida de `traffic.aggregate_traffic_by_municipality`
            con columnas (codigo, municipio, bw_total_mbps).

    Returns:
        DataFrame por nodo: codigo, municipio, tier, anillos_agregacion,
        anillos_troncal, bw_propio_mbps, bw_downstream_mbps,
        bw_acumulado_mbps, n_downstream_links.
    """
    # ---- bw_propio por nodo ----
    bw_propio: dict[str, float] = {n: 0.0 for n in graph.nodes()}
    cod_to_muni = {graph.nodes[n]["codigo"]: n for n in graph.nodes()}
    for _, row in df_traffic_per_muni.iterrows():
        m = cod_to_muni.get(int(row["codigo"]))
        if m is not None:
            bw_propio[m] = float(row["bw_total_mbps"])

    # ---- subgrafo sólo con aristas de acceso (hijo → padre) ----
    access_edges = [
        (u, v) for u, v, d in graph.edges(data=True)
        if d.get("tipo") == EDGE_ACCESS
    ]
    g_access = nx.DiGraph()
    g_access.add_nodes_from(graph.nodes())
    g_access.add_edges_from(access_edges)

    # n_downstream_links = predecesores inmediatos en el árbol de acceso.
    n_downstream_links: dict[str, int] = {
        n: g_access.in_degree(n) for n in graph.nodes()
    }

    # ---- pasada 1: acumulación por orden topológico (hojas → padres) ----
    bw_acumulado: dict[str, float] = dict(bw_propio)
    try:
        topo_order = list(nx.topological_sort(g_access))
    except nx.NetworkXUnfeasible as e:
        raise RuntimeError(
            "El subgrafo de acceso tiene ciclos; no se puede ordenar topológicamente."
        ) from e
    for node in topo_order:
        # Sumar BW de todos los predecesores (hijos en árbol de acceso).
        # Como el orden es topológico, los predecesores ya están actualizados.
        for pred in g_access.predecessors(node):
            bw_acumulado[node] += bw_acumulado[pred]

    # ---- pasada 2: cada anillo de agregación reenvía total al gateway ----
    for ring in _AGG_RINGS:
        members = [
            n for n, d in graph.nodes(data=True)
            if ring in d["anillos_agregacion"]
        ]
        if not members:
            continue
        gateway = _find_gateway(graph, members)
        if gateway is None:
            logger.warning("Anillo %s sin gateway claro; saltando.", ring)
            continue
        non_gateway = [m for m in members if m != gateway]
        ring_inflow = sum(bw_acumulado[m] for m in non_gateway)
        bw_acumulado[gateway] += ring_inflow
        # El gateway termina además los enlaces del anillo (link a cada otro miembro).
        n_downstream_links[gateway] += len(non_gateway)

    # ---- pasada 3: cada anillo troncal reenvía total a A900 ----
    for ring in _TRO_RINGS:
        members = [
            n for n, d in graph.nodes(data=True)
            if ring in d["anillos_troncal"]
        ]
        if not members or ROOT_NODE not in members:
            continue
        non_root = [m for m in members if m != ROOT_NODE]
        ring_inflow = sum(bw_acumulado[m] for m in non_root)
        bw_acumulado[ROOT_NODE] += ring_inflow
        n_downstream_links[ROOT_NODE] += len(non_root)

    # ---- DataFrame ----
    rows = []
    for n, d in graph.nodes(data=True):
        rows.append({
            "codigo": d["codigo"],
            "municipio": n,
            "tier": d["tier"],
            "anillos_agregacion": ",".join(sorted(d["anillos_agregacion"])) or "",
            "anillos_troncal": ",".join(sorted(d["anillos_troncal"])) or "",
            "bw_propio_mbps": bw_propio[n],
            "bw_downstream_mbps": bw_acumulado[n] - bw_propio[n],
            "bw_acumulado_mbps": bw_acumulado[n],
            "n_downstream_links": n_downstream_links[n],
        })
    df = pd.DataFrame(rows).sort_values("codigo").reset_index(drop=True)

    # Sanity check: bw_acumulado en A900 ≈ bw total del territorio.
    # Sólo aplicable si el grafo tiene la jerarquía completa (root presente).
    if ROOT_NODE in graph.nodes:
        bw_a900 = float(
            df.loc[df["municipio"] == ROOT_NODE, "bw_acumulado_mbps"].iloc[0]
        )
        bw_total = float(df_traffic_per_muni["bw_total_mbps"].sum())
        if not math.isclose(bw_a900, bw_total, rel_tol=1e-3):
            logger.warning(
                "Sanity check falló: bw A900=%.1f Mbps vs total=%.1f Mbps "
                "(gap=%.1f Mbps).",
                bw_a900, bw_total, bw_a900 - bw_total,
            )
        else:
            logger.info(
                "cumulative_traffic: A900=%.1f Gbps (=total territorio).",
                bw_a900 / 1000,
            )
    return df


def _find_gateway(graph: nx.DiGraph, members: list[str]) -> str | None:
    """Devuelve el miembro de un anillo de agregación que también pertenece
    a un anillo troncal (es decir, su gateway al backbone).

    Si A900 está entre los miembros, gana — cubre los anillos A1 y A2.
    """
    if ROOT_NODE in members:
        return ROOT_NODE
    for m in members:
        if graph.nodes[m]["anillos_troncal"]:
            return m
    return None


# ---------------------------------------------------------------------------
# select_equipment
# ---------------------------------------------------------------------------

def select_equipment(
    df_cumulative: pd.DataFrame,
    decisiones: dict,
    parametros: dict,
) -> pd.DataFrame:
    """Elige el equipo a desplegar en cada nodo y calcula su CAPEX.

    Args:
        df_cumulative: salida de `cumulative_traffic`.
        decisiones: configuración del escenario.
        parametros: dict de `load.load_parameters`.

    Returns:
        DataFrame: codigo, municipio, tier, equipo_principal, n_unidades,
        capex_equipo, capex_chasis, capex_extra, capex_total_nodo.
    """
    # ---- unitarios ----
    capex = parametros["capex"]
    p_chasis = float(capex["nodo_chasis"])
    p_cliente = float(capex["equipo_cliente"])
    p_10p = float(capex["equipo_agreg_10p"])
    p_20p = float(capex["equipo_agreg_20p"])
    p_40p = float(capex["equipo_agreg_40p"])
    p_mpls = float(capex["equipo_troncal_mpls"])
    p_optico = float(capex["equipo_troncal_optico_40l"])

    # ---- umbrales ----
    eq_cfg = decisiones["equipos"]
    u_10_20 = int(eq_cfg["umbral_10p_a_20p"])
    u_20_40 = int(eq_cfg["umbral_20p_a_40p"])
    u_40_mpls = int(eq_cfg["umbral_40p_a_mpls"])

    # Factor de creixement del 20% — dimensionem per tràfic futur
    factor_creixement = float(eq_cfg.get("factor_creixement", 1.2))

    # ---- DC A900 ----
    dc_capex_extra = float(decisiones.get("datacenter_a900", {}).get("capex_extra", 0))

    # ---- topology de soporte para sedes_abast (no viene en df_cumulative) ----
    rows = []
    for _, r in df_cumulative.iterrows():
        codigo = int(r["codigo"])
        muni = r["municipio"]
        tier = r["tier"]
        bw = float(r["bw_acumulado_mbps"])
        n_links = int(r["n_downstream_links"])

        if tier == "acceso":
            # Switch municipal: 1 port per seu + 1 majorista + 1 uplink, ×1.2
            sedes = int(r.get("sedes_abast", 0))
            if sedes > 0:
                ports_dim = math.ceil((sedes + 2) * factor_creixement)
                equipo, n_uds, capex_eq = _pick_switch_municipal(
                    ports_dim, u_10_20, u_20_40, u_40_mpls,
                    p_10p, p_20p, p_40p,
                )
            else:
                equipo, n_uds, capex_eq = ("sense_switch", 0, 0.0)
            capex_chasis = 0.0
            capex_extra = 0.0

        elif tier == "agregacion":
            # Aplicar factor de creixement als dos criteris de selecció
            bw_dim = bw * factor_creixement
            n_links_dim = math.ceil(n_links * factor_creixement)
            equipo, n_uds, capex_eq = _pick_aggregation(
                n_links_dim, bw_dim, u_10_20, u_20_40, u_40_mpls,
                p_10p, p_20p, p_40p, p_mpls, p_optico, muni,
            )
            capex_chasis = p_chasis
            capex_extra = 0.0

        elif tier == "troncal":
            equipo = "mpls + optico_40l"
            n_uds = 1
            capex_eq = p_mpls + p_optico
            capex_chasis = p_chasis
            capex_extra = dc_capex_extra if muni == ROOT_NODE else 0.0

        else:
            raise ValueError(f"Tier desconocido para {muni!r}: {tier!r}")

        capex_total = capex_eq + capex_chasis + capex_extra
        rows.append({
            "codigo": codigo,
            "municipio": muni,
            "tier": tier,
            "equipo_principal": equipo,
            "n_unidades": n_uds,
            "capex_equipo": capex_eq,
            "capex_chasis": capex_chasis,
            "capex_extra": capex_extra,
            "capex_total_nodo": capex_total,
        })

    df = pd.DataFrame(rows).sort_values("codigo").reset_index(drop=True)
    return df


def _pick_switch_municipal(
    ports_dim: int,
    u_10_20: int, u_20_40: int, u_40_mpls: int,
    p_10p: float, p_20p: float, p_40p: float,
) -> tuple[str, int, float]:
    """Switch local al municipi: tria el més petit que cobreix els ports.

    ports_dim = (sedes_abast + 1 majorista + 1 uplink) × 1.2 (ja aplicat).
    No s'usa MPLS aquí — màxim 40p per municipi d'accés.
    """
    if ports_dim <= u_10_20:
        return "switch_10p", 1, p_10p
    if ports_dim <= u_20_40:
        return "switch_20p", 1, p_20p
    return "switch_40p", 1, p_40p


def _pick_aggregation(
    n_links: int, bw_mbps: float,
    u_10_20: int, u_20_40: int, u_40_mpls: int,
    p_10p: float, p_20p: float, p_40p: float, p_mpls: float, p_optico: float,
    muni: str,
) -> tuple[str, int, float]:
    """Elige el equipo de agregación más pequeño que cumple AMBOS criterios:
    nº de puertos (n_links contra umbrales) y capacidad nominal (bw_mbps).

    Escalado en cascada (sin warnings: el escalado es la decisión correcta):
        10p → 20p → 40p → MPLS + N×40p → MPLS + N×40p + óptico 40λ.
    """
    if n_links <= u_10_20 and bw_mbps <= _CAPACIDAD_AGREG_10P_MBPS:
        return "agreg_10p", 1, p_10p
    if n_links <= u_20_40 and bw_mbps <= _CAPACIDAD_AGREG_20P_MBPS:
        return "agreg_20p", 1, p_20p
    if n_links <= u_40_mpls and bw_mbps <= _CAPACIDAD_AGREG_40P_MBPS:
        return "agreg_40p", 1, p_40p

    # Volumen alto: MPLS + N cajas 40p en paralelo (+ óptico si excede MPLS).
    n_40p_uds = max(
        math.ceil(n_links / 40),
        math.ceil(bw_mbps / _CAPACIDAD_AGREG_40P_MBPS),
        1,
    )
    capex = p_mpls + n_40p_uds * p_40p
    equipo = f"mpls + {n_40p_uds}×agreg_40p"
    n_uds = n_40p_uds + 1
    if bw_mbps > _CAPACIDAD_MPLS_MBPS:
        capex += p_optico
        equipo += " + optico_40l"
        n_uds += 1
    return equipo, n_uds, capex


# ---------------------------------------------------------------------------
# total_capex_equipos
# ---------------------------------------------------------------------------

def total_capex_equipos(df_equipment: pd.DataFrame) -> dict:
    """Resumen global del CAPEX de equipos.

    Args:
        df_equipment: salida de `assign_equipment` (con `equipo_cliente_capex`).

    Returns:
        dict con totales por categoría: equipo_cliente, equipo_agregacion,
        equipo_troncal, chasis, datacenter_a900, total.
    """
    cliente = float(df_equipment.get("equipo_cliente_capex", pd.Series(0.0)).sum())
    agreg = float(
        df_equipment.loc[df_equipment["tier"] == "agregacion", "capex_equipo"].sum()
    )
    troncal = float(
        df_equipment.loc[df_equipment["tier"] == "troncal", "capex_equipo"].sum()
    )
    chasis = float(df_equipment["capex_chasis"].sum())
    dc_extra = float(df_equipment["capex_extra"].sum())
    total = cliente + agreg + troncal + chasis + dc_extra

    return {
        "equipo_cliente": cliente,
        "equipo_agregacion": agreg,
        "equipo_troncal": troncal,
        "chasis": chasis,
        "datacenter_a900": dc_extra,
        "total": total,
    }


# ---------------------------------------------------------------------------
# assign_equipment — wrapper end-to-end usado por main.py
# ---------------------------------------------------------------------------

def assign_equipment(
    graph: nx.DiGraph,
    traffic: pd.DataFrame,
    decisiones: dict,
    parametros: dict | None = None,
) -> pd.DataFrame:
    """Wrapper end-to-end: tráfico acumulado + selección de equipo + CAPEX.

    Args:
        graph: grafo de `topology.build_graph`.
        traffic: salida de `traffic.compute_traffic` (codigo, municipio,
            bw_abast_mbps, bw_mayorista_mbps, bw_total_mbps).
        decisiones: configuración del escenario.
        parametros: dict de `load.load_parameters`. Obligatorio para
            calcular CAPEX (si es None, raisea).

    Returns:
        DataFrame por nodo con todas las columnas relevantes:
        codigo, municipio, tier, anillos_*, bw_propio_mbps,
        bw_downstream_mbps, bw_acumulado_mbps, n_downstream_links,
        sedes_abast, equipo_cliente_capex, equipo_principal, n_unidades,
        capex_equipo, capex_chasis, capex_extra, capex_total_nodo.
    """
    if parametros is None:
        raise ValueError("`parametros` es obligatorio para calcular CAPEX.")

    df_cum = cumulative_traffic(graph, traffic)

    # Inyectar sedes_abast ANTES de select_equipment (necesario para switch municipal)
    sedes_by_muni = {n: graph.nodes[n].get("sedes_abast", 0) for n in graph.nodes()}
    df_cum["sedes_abast"] = df_cum["municipio"].map(sedes_by_muni).astype(int)

    df_eq = select_equipment(df_cum, decisiones, parametros)

    # CAPEX equip client (CPE per seu) — calculat des de sedes_by_muni
    p_cliente = float(parametros["capex"]["equipo_cliente"])
    df_eq["sedes_abast"] = df_eq["municipio"].map(sedes_by_muni).astype(int)
    df_eq["equipo_cliente_capex"] = df_eq["sedes_abast"].astype(float) * p_cliente
    df_eq["capex_total_nodo"] = (
        df_eq["capex_total_nodo"] + df_eq["equipo_cliente_capex"]
    )

    # Merge — excloure sedes_abast de df_cum per evitar duplicat _x/_y
    df_cum_merge = df_cum.drop(columns=["sedes_abast"], errors="ignore")
    df = df_cum_merge.merge(
        df_eq[[
            "codigo", "equipo_principal", "n_unidades",
            "capex_equipo", "capex_chasis", "capex_extra",
            "sedes_abast", "equipo_cliente_capex", "capex_total_nodo",
        ]],
        on="codigo", how="left",
    )

    totals = total_capex_equipos(df)
    logger.info(
        "assign_equipment: CAPEX equipos = %.2f M€ "
        "(cliente=%.1f, agregación=%.1f, troncal=%.1f, chasis=%.1f, DC=%.1f)",
        totals["total"] / 1e6,
        totals["equipo_cliente"] / 1e6,
        totals["equipo_agregacion"] / 1e6,
        totals["equipo_troncal"] / 1e6,
        totals["chasis"] / 1e6,
        totals["datacenter_a900"] / 1e6,
    )
    return df

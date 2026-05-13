"""opex.py — costes operativos plurianuales.

Suma mantenimiento de fibra (250 €/km·año × km activos), mantenimiento
de equipos (10% del CAPEX activo acumulado), mantenimiento SI (0.5% del
CAPEX acumulado), local técnic de nodos, datacenter A900, RRHH,
derechos de paso e impuestos (3% ingresos), costes de venta mayorista
(10% de ingresos mayorista) y gastos generales (700.000 €/año).

Todo el OPEX se escala con inflación = (1+0.02)^(anio-1).

Función pública:
    compute_opex(capex_df, df, revenue_df, decisiones, parametros)
        -> pd.DataFrame
"""

from __future__ import annotations

import logging
import math

import pandas as pd

from src.capex import _deployment_schedule

logger = logging.getLogger(__name__)

_N_ANIOS = 20
# Nodos de agregación y troncal son fijos desde el año 1
_N_AGREG = 91
_N_TRONCAL_SIN_DC = 9   # A891–A899 (A900 tiene datacenter propio)


def compute_opex(
    capex_df: pd.DataFrame,
    df: pd.DataFrame,
    revenue_df: pd.DataFrame,
    decisiones: dict,
    parametros: dict,
) -> pd.DataFrame:
    """Calcula el OPEX plurianual.

    Columnas de salida:
        anio, mant_fibra_eur, mant_equipos_eur, mant_si_eur,
        opex_local_tecnic_eur, opex_datacenter_eur, rrhh_eur,
        gastos_generales_eur, derechos_paso_eur, costes_ventas_mayo_eur,
        total_eur

    Args:
        capex_df: salida de `capex.compute_capex` (para CAPEX acumulado).
        df: DataFrame de topología (para km activos).
        revenue_df: salida de `revenue.compute_revenue` (para ingresos).
        decisiones: configuración del escenario.
        parametros: tarifas y costes unitarios.

    Returns:
        DataFrame de 20 filas.
    """
    if capex_df is None or revenue_df is None:
        logger.warning("compute_opex: capex_df o revenue_df es None; retornando vacío.")
        return pd.DataFrame(columns=[
            "anio", "mant_fibra_eur", "mant_equipos_eur", "mant_si_eur",
            "opex_local_tecnic_eur", "opex_datacenter_eur", "rrhh_eur",
            "gastos_generales_eur", "derechos_paso_eur", "costes_ventas_mayo_eur",
            "total_eur",
        ])

    # ---- parámetros ----
    opex_p = parametros["opex"]
    mant_fibra_km_año = float(opex_p["mant_fibra_eur_km_año"])       # 250 €/km/año
    mant_equip_pct = float(opex_p["mant_equipos_pct_capex"])         # 0.10
    mant_si_pct_capex = float(opex_p["mant_si_pct_capex"]) * 0.05   # 10% sobre SI~5%CAPEX → 0.5%
    derechos_paso_pct = float(opex_p["derechos_paso_pct_ingresos"])  # 0.03
    costes_ventas_pct = float(opex_p["costes_ventas_mayorista_pct"]) # 0.10
    gastos_generales = float(opex_p["gastos_generales_anuales"])     # 700.000

    # ---- local técnic nodos (fijos desde año 1) ----
    infra_cfg = decisiones.get("infraestructura_nodes", {})
    opex_local_agreg = float(infra_cfg.get("agregacio", {}).get("opex_anual_eur", 3000))
    opex_local_troncal = float(infra_cfg.get("troncal", {}).get("opex_anual_eur", 8000))
    opex_local_acceso = float(infra_cfg.get("acceso", {}).get("opex_anual_eur", 200))

    opex_local_fijo = (
        _N_AGREG * opex_local_agreg
        + _N_TRONCAL_SIN_DC * opex_local_troncal
    )

    # ---- datacenter A900 ----
    opex_datacenter_anual = float(
        decisiones.get("datacenter_a900", {}).get("opex_extra_anual", 500_000)
    )

    # ---- RRHH ----
    rrhh = decisiones.get("rrhh", {})
    emp_noc = int(rrhh.get("empleados_base_noc", 5))
    emp_admin = int(rrhh.get("empleados_base_admin", 10))
    ratio_km = float(rrhh.get("ratio_km_por_empleado_campo", 200))
    ratio_sedes = float(rrhh.get("ratio_sedes_por_empleado_soporte", 500))
    salario = float(rrhh.get("salario_medio_empleado", 50_000))

    # ---- inflación ----
    inflacion = float(decisiones.get("contingencia", {}).get("inflacion_anual", 0.02))

    # ---- schedule de despliegue ----
    schedule = _deployment_schedule(df, decisiones)
    df_acc = df[df["tier"] == "acceso"].set_index("municipio")

    # ---- separar CAPEX de equipos vs obra civil en capex_df ----
    # mant_equipos aplica sólo al CAPEX de equipos (no a obra civil ni altas)
    # Las columnas relevantes son: equipos_acceso_eur + infra_agregacio_eur
    # (la infra_agregacio incluye chasis y equipos de nodos agg/troncal)
    has_equip_col = (
        "equipos_acceso_eur" in capex_df.columns
        and "infra_agregacio_eur" in capex_df.columns
    )

    # ---- construir mapa anio → km acumulado y sedes_abast activas ----
    # Precalcular km y sedes por año de conexión
    km_por_anio: dict[int, float] = {a: 0.0 for a in range(1, _N_ANIOS + 1)}
    sedes_por_anio: dict[int, int] = {a: 0 for a in range(1, _N_ANIOS + 1)}
    munis_por_anio: dict[int, int] = {a: 0 for a in range(1, _N_ANIOS + 1)}

    # Sedes de nodos no-acceso (activos desde año 1)
    sedes_no_acceso = int(
        df[df["tier"].isin(["agregacion", "troncal"])]["sedes_abast"].sum()
    )

    for m, y in schedule.items():
        if m in df_acc.index:
            km_por_anio[y] = km_por_anio.get(y, 0.0) + float(df_acc.loc[m, "km"])
            sedes_por_anio[y] = sedes_por_anio.get(y, 0) + int(df_acc.loc[m, "sedes_abast"])
            munis_por_anio[y] = munis_por_anio.get(y, 0) + 1

    # ---- revenue indexado por año ----
    rev_by_anio = revenue_df.set_index("anio")

    # ---- iterar 20 años ----
    rows = []
    km_acum = 0.0
    sedes_abast_acum = sedes_no_acceso  # no-acceso activos desde año 1
    n_acc_active = 0
    capex_acum = 0.0
    capex_equipos_acum = 0.0  # sólo equipos (no obra civil)

    for anio in range(1, _N_ANIOS + 1):
        # Actualizar acumulados
        km_acum += km_por_anio.get(anio, 0.0)
        sedes_abast_acum += sedes_por_anio.get(anio, 0)
        n_acc_active += munis_por_anio.get(anio, 0)
        capex_row = capex_df.loc[capex_df["anio"] == anio]
        capex_anio = float(capex_row["total_eur"].iloc[0])
        capex_acum += capex_anio

        # CAPEX equipos acumulado (para mant_equipos)
        if has_equip_col:
            eq_anio = (
                float(capex_row["equipos_acceso_eur"].iloc[0])
                + float(capex_row["infra_agregacio_eur"].iloc[0])
            )
        else:
            # Fallback: 10% del total (menos obra civil aprox)
            eq_anio = capex_anio * 0.08  # rough estimate
        capex_equipos_acum += eq_anio

        # Factor inflación
        inf_factor = (1 + inflacion) ** (anio - 1)

        # Mantenimiento fibra
        mant_fibra = km_acum * mant_fibra_km_año

        # Mantenimiento equipos activos (10% CAPEX equipos acumulado, no obra civil)
        mant_equipos = capex_equipos_acum * mant_equip_pct

        # Mantenimiento SI (~0.5% CAPEX equipos acumulado)
        mant_si = capex_equipos_acum * mant_si_pct_capex

        # Local técnic nodos fijos + nodos acceso activos
        opex_local = opex_local_fijo + n_acc_active * opex_local_acceso

        # Datacenter
        opex_dc = opex_datacenter_anual

        # RRHH
        emp_campo = math.ceil(km_acum / ratio_km) if km_acum > 0 else 0
        emp_soporte = math.ceil(sedes_abast_acum / ratio_sedes) if sedes_abast_acum > 0 else 0
        n_empleados = emp_noc + emp_admin + emp_campo + emp_soporte
        rrhh_coste = n_empleados * salario

        # Gastos generales
        gg = gastos_generales

        # Aplicar inflación a los costes operativos (no a derechos/costes ventas
        # que dependen de ingresos ya nominales)
        mant_fibra_inf = mant_fibra * inf_factor
        mant_equipos_inf = mant_equipos * inf_factor
        mant_si_inf = mant_si * inf_factor
        opex_local_inf = opex_local * inf_factor
        opex_dc_inf = opex_dc * inf_factor
        rrhh_inf = rrhh_coste * inf_factor
        gg_inf = gg * inf_factor

        # Derechos de paso e impuestos = 3% ingresos totales
        ing_total = float(rev_by_anio.loc[anio, "total_eur"]) if anio in rev_by_anio.index else 0.0
        ing_mayo = (
            float(rev_by_anio.loc[anio, "ingresos_mayo_alta_eur"])
            + float(rev_by_anio.loc[anio, "ingresos_mayo_rec_eur"])
        ) if anio in rev_by_anio.index else 0.0

        derechos_paso = ing_total * derechos_paso_pct
        costes_ventas_mayo = ing_mayo * costes_ventas_pct

        total = (
            mant_fibra_inf
            + mant_equipos_inf
            + mant_si_inf
            + opex_local_inf
            + opex_dc_inf
            + rrhh_inf
            + gg_inf
            + derechos_paso
            + costes_ventas_mayo
        )

        rows.append({
            "anio": anio,
            "mant_fibra_eur": round(mant_fibra_inf),
            "mant_equipos_eur": round(mant_equipos_inf),
            "mant_si_eur": round(mant_si_inf),
            "opex_local_tecnic_eur": round(opex_local_inf),
            "opex_datacenter_eur": round(opex_dc_inf),
            "rrhh_eur": round(rrhh_inf),
            "gastos_generales_eur": round(gg_inf),
            "derechos_paso_eur": round(derechos_paso),
            "costes_ventas_mayo_eur": round(costes_ventas_mayo),
            "total_eur": round(total),
        })

    opex_df = pd.DataFrame(rows)

    logger.info(
        "compute_opex: OPEX total 20 años = %.2f M€; año 20 = %.2f M€",
        opex_df["total_eur"].sum() / 1e6,
        opex_df.iloc[-1]["total_eur"] / 1e6,
    )
    return opex_df

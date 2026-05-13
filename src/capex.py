"""capex.py — inversiones (CAPEX) por año.

Combina obra civil (€/m), altas de sede (ABAST y mayorista), chasis de
nodos, equipos seleccionados por `equipment.py`, y el CAPEX extra del
datacenter A900. Agrega los totales por año siguiendo el plan de
despliegue (`decisiones.despliegue`).

Funciones públicas:
    _alpha(anio, alpha_obj, anios_rampa) -> float
    _deployment_schedule(df, decisiones) -> dict[str, int]
    compute_capex(df, equipment_df, decisiones, parametros) -> pd.DataFrame
"""

from __future__ import annotations

import logging
import math

import pandas as pd

logger = logging.getLogger(__name__)

_N_ANIOS = 20


# ---------------------------------------------------------------------------
# _alpha — rampa de cuota mayorista
# ---------------------------------------------------------------------------

def _alpha(anio: int, alpha_obj: float, anios_rampa: int) -> float:
    """Fracción de cuota mayorista en el año dado.

    Args:
        anio: año de la concesión (1..20).
        alpha_obj: cuota objetivo en régimen estacionario.
        anios_rampa: años para alcanzar la cuota objetivo.

    Returns:
        alpha ∈ [0, alpha_obj].
    """
    if anio <= 0:
        return 0.0
    t = min(anio / max(anios_rampa, 1), 1.0)
    return alpha_obj * t


# ---------------------------------------------------------------------------
# _deployment_schedule — orden y año de conexión de cada municipio de acceso
# ---------------------------------------------------------------------------

def _deployment_schedule(df: pd.DataFrame, decisiones: dict) -> dict[str, int]:
    """Asigna el año de conexión (1–20) a cada municipio de acceso.

    Ordena los municipios de acceso por (sedes_abast DESC, hab DESC)
    y los va agrupando por año hasta que se llega al tope de km anuales
    configurado en `decisiones.despliegue.km_max_anuales`.

    Los nodos de agregación y troncal se asignan al año 0 (ya están en
    año 1 en el CAPEX de infraestructura, pero no entran aquí).

    Args:
        df: DataFrame de topología (con columnas municipio, tier, km,
            sedes_abast, hab).
        decisiones: configuración del escenario.

    Returns:
        dict municipio → año de conexión (1..20).
        Los nodos agregacion/troncal no aparecen en el dict.
    """
    km_max = float(decisiones["despliegue"].get("km_max_anuales", 500))

    # Solo municipios de acceso
    acceso = df[df["tier"] == "acceso"].copy()
    # Orden de prioridad: sedes_abast desc, hab desc
    acceso = acceso.sort_values(
        ["sedes_abast", "hab"], ascending=[False, False]
    ).reset_index(drop=True)

    schedule: dict[str, int] = {}
    km_acum = 0.0
    anio_actual = 1

    for _, row in acceso.iterrows():
        muni = str(row["municipio"])
        km_muni = float(row["km"])

        # Si añadir este municipio supera el tope del año, pasamos al siguiente
        if km_acum + km_muni > km_max and km_acum > 0:
            anio_actual += 1
            km_acum = 0.0

        # Nunca superar el año 20
        anio_actual = min(anio_actual, _N_ANIOS)
        schedule[muni] = anio_actual
        km_acum += km_muni

    return schedule


# ---------------------------------------------------------------------------
# compute_capex
# ---------------------------------------------------------------------------

def compute_capex(
    df: pd.DataFrame,
    equipment_df: pd.DataFrame,
    decisiones: dict,
    parametros: dict,
) -> pd.DataFrame:
    """Calcula el CAPEX por año durante los 20 años de concesión.

    Columnas de salida:
        anio, obra_civil_eur, altas_abast_eur, altas_mayorista_eur,
        equipos_acceso_eur, infra_agregacio_eur, total_eur

    Lógica:
    - Año 1: toda la infraestructura de agregación y troncal (chasis +
      equipo de los nodos tier='agregacion' y 'troncal' + datacenter A900).
    - Años 1..20: cada municipio de acceso conecta en el año que le
      corresponde según _deployment_schedule. Ese año se carga:
          * obra_civil = km × 1000 × 100 €/m  (km → metros)
          * altas_abast = sedes_abast × 20.000 €
          * altas_mayorista = nuevas_sedes_mayo × 1.500 € (alta mayorista)
          * equipos_acceso = capex_total_nodo del municipio (del equipment_df)

    Mayorista: sedes_mayo(muni, anio) = num_operadores × alpha(anio) ×
    penetracion_fibra. Las "nuevas sedes" de un año son (a) las de los
    municipios que conectan ese año + (b) el incremento de la rampa en
    municipios ya conectados.

    Args:
        df: DataFrame de topología.
        equipment_df: salida de `equipment.assign_equipment`.
        decisiones: configuración del escenario.
        parametros: tarifas y costes unitarios.

    Returns:
        DataFrame de 20 filas (una por año).
    """
    # ---- parámetros ----
    cap = parametros["capex"]
    obra_civil_eur_m = float(cap["obra_civil_acceso_eur_m"])   # €/m
    alta_abast_eur = float(cap["alta_sede_abast"])              # €/sede
    alta_mayo_eur = float(parametros["ingresos"]["alta_mayorista"])  # €/sede
    contingencia_pct = float(
        decisiones.get("contingencia", {}).get("reserva_imprevistos_pct", 0.0)
    )

    # ---- mayorista params ----
    mayo_cfg = decisiones["mayorista"]["cuota_mercado"]
    alpha_obj = float(mayo_cfg["alpha_objetivo"])
    anios_rampa = int(mayo_cfg.get("anios_rampa", 8))
    penetracion = float(decisiones["mayorista"].get("penetracion_fibra_pct", 0.70))

    # ---- schedule de despliegue ----
    schedule = _deployment_schedule(df, decisiones)

    # ---- equipos por municipio (acceso) ----
    eq_acceso = (
        equipment_df[equipment_df["tier"] == "acceso"]
        .set_index("municipio")["capex_total_nodo"]
        .to_dict()
    )

    # ---- infra año 1: agregacion + troncal ----
    infra_yr1 = float(
        equipment_df[equipment_df["tier"].isin(["agregacion", "troncal"])][
            "capex_total_nodo"
        ].sum()
    )

    # ---- topología: datos por municipio de acceso ----
    df_acc = df[df["tier"] == "acceso"].set_index("municipio")

    # ---- sedes y mayorista de nodos no-acceso (año 1) ----
    df_no_acc = df[df["tier"].isin(["agregacion", "troncal"])].set_index("municipio")
    sedes_no_acceso = int(df_no_acc["sedes_abast"].sum())
    # Mayorista no-acceso año 1
    mayo_no_acc_yr1 = sum(
        int(row["num_operadores"]) * _alpha(1, alpha_obj, anios_rampa) * penetracion
        for _, row in df_no_acc.iterrows()
    )

    # ---- iterar 20 años ----
    rows = []
    # Acumulamos las sedes mayoristas ya activas por municipio
    sedes_mayo_previas: dict[str, float] = {}

    for anio in range(1, _N_ANIOS + 1):
        # Municipios que conectan ESTE año
        new_munis = [m for m, y in schedule.items() if y == anio]

        # Obra civil
        km_anio = sum(
            float(df_acc.loc[m, "km"]) for m in new_munis if m in df_acc.index
        )
        obra_civil = km_anio * 1000 * obra_civil_eur_m  # km→m

        # Altas ABAST (acceso + nodos no-acceso en año 1)
        sedes_nuevas = sum(
            int(df_acc.loc[m, "sedes_abast"]) for m in new_munis if m in df_acc.index
        )
        if anio == 1:
            sedes_nuevas += sedes_no_acceso
        altas_abast = sedes_nuevas * alta_abast_eur

        # Altas mayorista = nuevas sedes de municipios que conectan +
        #                   incremento de rampa en municipios ya activos
        alpha_ahora = _alpha(anio, alpha_obj, anios_rampa)
        alpha_antes = _alpha(anio - 1, alpha_obj, anios_rampa)

        nuevas_sedes_mayo = 0.0

        # Nodos no-acceso: altas en año 1
        if anio == 1:
            nuevas_sedes_mayo += mayo_no_acc_yr1
            # registrar en previas para calculo de incremento posterior
            for m_na, row_na in df_no_acc.iterrows():
                n_op_na = int(row_na["num_operadores"])
                sedes_mayo_previas[str(m_na)] = n_op_na * alpha_ahora * penetracion

        # Municipios que conectan este año (su alpha anterior era 0)
        for m in new_munis:
            if m not in df_acc.index:
                continue
            n_op = int(df_acc.loc[m, "num_operadores"])
            sedes_m = n_op * alpha_ahora * penetracion
            sedes_mayo_previas[m] = sedes_m
            nuevas_sedes_mayo += sedes_m  # alta única al conectar

        # Municipios ya conectados: incremento por rampa
        already_active = [m for m, y in schedule.items() if y < anio]
        for m in already_active:
            if m not in df_acc.index:
                continue
            n_op = int(df_acc.loc[m, "num_operadores"])
            sedes_ahora_m = n_op * alpha_ahora * penetracion
            sedes_antes_m = sedes_mayo_previas.get(m, n_op * alpha_antes * penetracion)
            incremento = max(sedes_ahora_m - sedes_antes_m, 0.0)
            nuevas_sedes_mayo += incremento
            sedes_mayo_previas[m] = sedes_ahora_m

        altas_mayorista = nuevas_sedes_mayo * alta_mayo_eur

        # Equipos de acceso
        equipos_acc = sum(
            float(eq_acceso.get(m, 0.0)) for m in new_munis
        )

        # Infra agregacion+troncal: sólo año 1
        infra_agg = infra_yr1 if anio == 1 else 0.0

        subtotal = obra_civil + altas_abast + altas_mayorista + equipos_acc + infra_agg
        # Contingencia (reserva imprevistos) sobre CAPEX bruto
        contingencia = subtotal * contingencia_pct
        total = subtotal + contingencia

        rows.append({
            "anio": anio,
            "obra_civil_eur": round(obra_civil),
            "altas_abast_eur": round(altas_abast),
            "altas_mayorista_eur": round(altas_mayorista),
            "equipos_acceso_eur": round(equipos_acc),
            "infra_agregacio_eur": round(infra_agg),
            "contingencia_eur": round(contingencia),
            "total_eur": round(total),
        })

    capex_df = pd.DataFrame(rows)

    total_20 = capex_df["total_eur"].sum()
    logger.info(
        "compute_capex: CAPEX total 20 años = %.2f M€ "
        "(infra_agg_yr1=%.1f M€, obra_civil=%.1f M€, "
        "altas_abast=%.1f M€, equipos=%.1f M€)",
        total_20 / 1e6,
        infra_yr1 / 1e6,
        capex_df["obra_civil_eur"].sum() / 1e6,
        capex_df["altas_abast_eur"].sum() / 1e6,
        capex_df["equipos_acceso_eur"].sum() / 1e6,
    )
    return capex_df

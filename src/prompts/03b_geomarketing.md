# Prompt 03b — Módulo `geomarketing.py`

> Asegúrate de que `traffic.py` (prompt 03) está terminado y los tests pasan.

Lee `CLAUDE.md` y `data/decisiones.yaml` (sección `geomarketing` e `infraestructura_acceso`) para entender el contexto completo.

## Objetivo

Generar el **análisis de viabilidad por municipio** que el profesor pidió en la TAREA 5: para cada uno de los 900 municipios, calcular el atractivo económico y técnico de desplegar la red ahí. Sirve para:

1. Defender la **estrategia y orden de despliegue** en la oferta técnica (qué municipios primero, cuáles después, cuáles dejar para el final).
2. Identificar municipios "no viables" si los hay (rara vez aplica aquí porque la cobertura es obligatoria al 100%, pero el análisis se exige aún así).
3. Estimar **ingresos potenciales por municipio** y **payback municipal** como input al modelo económico global.

## API a exponer

```python
import pandas as pd

def municipal_viability(
    df_topology: pd.DataFrame,
    df_traffic_abast: pd.DataFrame,
    df_traffic_mayorista: pd.DataFrame,
    parametros: dict,
    decisiones: dict,
) -> pd.DataFrame:
    """Análisis de viabilidad económica por municipio en régimen estacionario.

    Para cada municipio calcula:
        - Ingresos anuales potenciales (ABAST + mayorista residencial + PYMEs)
        - CAPEX estimado de despliegue local (obra civil + equipos + altas)
        - OPEX anual estimado
        - Payback municipal estimado (ignorando red troncal/agregación, sólo acceso)
        - Score de atractivo (combinado)
        - Flag de viable (cumple umbrales de decisiones['geomarketing']['viabilidad_minima'])

    Returns DataFrame: codigo, municipio, hab, sedes_abast, num_operadores,
                       ingresos_abast_anuales, ingresos_mayorista_resi_anuales,
                       ingresos_pymes_anuales, ingresos_total_anuales,
                       capex_local_estimado, opex_local_anual,
                       payback_municipal_anios, score_atractivo, viable
    """

def deployment_priority_order(
    df_viability: pd.DataFrame,
    decisiones: dict,
) -> pd.DataFrame:
    """Determina el ORDEN óptimo de despliegue de municipios según el criterio
    elegido en decisiones['geomarketing']['prioridad_despliegue']['criterio'].

    Returns DataFrame ordenado: orden_despliegue (1=primero), codigo, municipio,
                                criterio_valor, anio_objetivo_despliegue
    """

def pyme_estimation_per_municipality(
    df_topology: pd.DataFrame,
    decisiones: dict,
) -> pd.DataFrame:
    """Estimación del número de PYMEs por municipio usando ratio del INE.

    Fórmula:
        n_pymes = hab / habitantes_por_pyme
        clientes_pyme = n_pymes × penetracion_pyme_pct
        bw_pyme_mbps = clientes_pyme × bw_por_pyme_mbps / overbooking_empresa

    Returns DataFrame: codigo, n_pymes_estimadas, clientes_pyme, bw_pyme_mbps
    """

def infraestructura_acceso_por_municipio(
    df_topology: pd.DataFrame,
    decisiones: dict,
) -> pd.DataFrame:
    """Decide para cada municipio si se instala armario de calle o local cerrado,
    y calcula el coste asociado.

    Lógica:
        - Si decisiones['infraestructura_acceso']['tipo_punto_acceso'] == 'armario_calle':
            todos los munis usan armario, coste extra = coste_licencia_armario_eur (one-shot)
        - Si == 'local_cerrado': todos usan local, coste = alquiler_local_anual recurrente
        - Si == 'mixto':
            munis con hab >= umbral_hab_para_local_cerrado → local_cerrado
            munis con hab <  umbral_hab_para_local_cerrado → armario_calle

    Returns DataFrame: codigo, tipo_punto_acceso, capex_extra, opex_extra_anual
    """
```

## Lógica de ingresos potenciales por municipio (régimen estacionario)

```
ingresos_abast_anuales = sedes_abast × tarifa_recurrente_abast × 12
clientes_resi = (hab / hab_por_hogar) × cuota_operadores × penetracion_fibra
ingresos_mayorista_resi = clientes_resi × tarifa_recurrente_mayorista × 12
n_pymes = hab / hab_por_pyme
clientes_pyme = n_pymes × penetracion_pyme
ingresos_pymes = clientes_pyme × tarifa_pyme × 12   (tarifa_pyme ≈ 2× tarifa_resi)
ingresos_total = abast + resi + pymes
```

Para `cuota_operadores` aplicar la estrategia `'equilibrio'` (1/(num_op+1)) en este análisis a régimen estacionario, ignorando rampa temporal — es lo más conservador.

## Lógica de CAPEX local estimado

```
capex_obra_civil_local = km_aproximados_internos × 100 €/m × 1000
capex_altas = sedes_abast × 20.000 + clientes_resi × 20.000 + clientes_pyme × 20.000
capex_punto_acceso = coste_licencia_armario  O  capex_alquiler_local (no aplica aquí, es OPEX)
capex_local_total = obra_civil + altas + punto_acceso
```

Para `km_aproximados_internos` por municipio podemos usar el `km` de la columna del Excel del enlace al destino_acceso, multiplicado por un factor de 1.5 para reflejar la red interna del muni (estimación grosera pero defendible).

## Lógica de payback municipal

```
margen_anual_local = ingresos_total_anuales − opex_local_anual
payback = capex_local_estimado / margen_anual_local
Si margen_anual_local <= 0:
    payback = inf (muni no viable por flujo de caja negativo)
```

## Score de atractivo

Combinación ponderada normalizada (0–100) de:
- Ingresos anuales potenciales (peso 50%)
- Payback corto (peso 30%, invertido: payback bajo = score alto)
- Densidad de PYMEs (peso 10%)
- Baja competencia (peso 10%, invertido: pocos operadores = score alto)

## Flag de viabilidad

`viable = True` si:
- `ingresos_total_anuales >= decisiones['geomarketing']['viabilidad_minima']['ingresos_anuales_min_eur']`
- `payback_municipal_anios <= decisiones['geomarketing']['viabilidad_minima']['payback_municipal_max_anios']`

Recordar que aunque un municipio salga con `viable=False`, **igual hay que conectarlo** porque la cobertura es obligatoria al 100% según las bases del concurso. El flag sirve para documentación, no para excluir.

## Validaciones

- Suma de `ingresos_abast_anuales` ≈ 5.000 sedes × 12.000 €/año = **60 M€/año** (sanity check).
- A900 debe tener el `score_atractivo` más alto (769 sedes, 2M habitantes).
- Reportar municipios con `viable = False` si los hay.

## Tests mínimos

- `municipal_viability` produce 900 filas.
- `pyme_estimation_per_municipality` con 10.000 hab y `habitantes_por_pyme=50` da 200 PYMEs.
- `deployment_priority_order` con criterio `ingresos_potenciales_descendente` pone A900 en primera posición.
- `infraestructura_acceso_por_municipio` con tipo `mixto` y umbral 20.000 hab clasifica correctamente A900 (local_cerrado) y un muni rural (armario_calle).

## Cuando termines

- Reportar el número de municipios viables / no viables.
- Reportar A900, A1, A11 con sus scores y payback.
- Pasar al prompt 04 (`equipment.py`).

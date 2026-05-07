# Prompt 03 — Módulo `traffic.py`

> Asegúrate de que `topology.py` está terminado.

Lee `CLAUDE.md` para el contexto. Especialmente la sección **Decisiones del grupo** y **Flujo de cálculo paso 3 y 4**.

## Objetivo

Calcular el tráfico (en Mbps) que genera cada municipio, separado en:
- **Tráfico ABAST** (autoprestación, determinístico, sin decisiones)
- **Tráfico mayorista** (con tres decisiones del grupo: cuota α, BW por hogar, overbooking)

El resultado son DataFrames por municipio que después `equipment.py` agrega aguas arriba en el árbol.

## API a exponer

```python
import pandas as pd
import networkx as nx

def traffic_abast(df_topology: pd.DataFrame, decisiones: dict) -> pd.DataFrame:
    """Tráfico ABAST por municipio.
    
    Fórmula:
        bw_mbps = sedes_abast × bw_por_sede_mbps / overbooking_abast
    
    Returns DataFrame: codigo, municipio, sedes_abast, bw_abast_mbps
    
    Para ABAST por defecto overbooking_abast = 1 (sin overbooking, sedes 
    críticas con BW garantizado).
    """

def traffic_mayorista(
    df_topology: pd.DataFrame,
    decisiones: dict,
    año: int = 20,
) -> pd.DataFrame:
    """Tráfico mayorista por municipio en el año dado.

    Fórmula (según pizarra del profesor 07/05/2026):
        hogares_teoricos = hab / habitantes_por_hogar
        cuota_operadores = _cuota(num_operadores, año, decisiones)
        clientes = hogares_teoricos × cuota_operadores × penetracion_fibra_pct
        bw_mbps = clientes × bw_por_hogar_mbps / overbooking

    Donde:
        - cuota_operadores: cómo nos repartimos el mercado entre los operadores
          ya presentes (estrategia equilibrio/agresivo/rampa).
        - penetracion_fibra_pct: % de hogares del municipio que efectivamente
          contratan fibra (no todos los hogares contratan; algunos siguen
          con cable, ADSL o sólo móvil).

    Returns DataFrame: codigo, municipio, hogares_teoricos, cuota_operadores,
                       penetracion_fibra, clientes_mayorista, bw_mayorista_mbps
    """

def _cuota_alpha(num_operadores: int, año: int, decisiones: dict) -> float:
    """Calcula la cuota de mercado mayorista según la estrategia elegida.
    
    Tres estrategias (decisiones['mayorista']['cuota_mercado']['tipo']):
        - 'equilibrio':  α = 1 / (num_operadores + 1)  -- entramos como uno más
        - 'agresivo':    α = 1 / num_operadores         -- desplazamos a uno
        - 'rampa':       α(año) = α_objetivo × min(año / años_rampa, 1)
    """

def aggregate_traffic_by_municipality(
    df_abast: pd.DataFrame, 
    df_mayorista: pd.DataFrame,
) -> pd.DataFrame:
    """Junta ABAST + mayorista por municipio.
    
    Returns DataFrame: codigo, municipio, bw_abast_mbps, bw_mayorista_mbps,
                       bw_total_mbps
    """
```

> **Importante**: la fórmula desglosa explícitamente **cuota entre operadores** y **penetración de fibra** como dos factores independientes. Antes de la pizarra del 07/05 las dos cosas estaban mezcladas en un único `alpha`. Esta separación permite analizar sensibilidad por cada factor por separado, y refleja la realidad: no todos los hogares contratan fibra (penetración) Y de los que contratan, sólo una fracción es nuestra (cuota).

Las funciones `traffic_abast`, `_cuota_alpha` y `aggregate_traffic_by_municipality` no cambian respecto a la versión anterior del prompt.

## Validaciones

- En `_cuota_alpha`, garantizar que α ∈ [0, 1] sea cual sea la combinación de inputs.
- Si `num_operadores == 0` (no debería pasar en estos datos, pero por defensa), tratar como `1`.
- Si `año == 0`, devolver α = 0 para mayorista (todavía no hemos entrado al mercado).
- El BW total agregado del territorio en el año 20 con escenario base debería rondar **500 Gbps de ABAST + ~50–100 Gbps de mayorista** (depende de las decisiones). Reporta este número como sanity check.

## Tests mínimos

- `traffic_abast` para el municipio A900 (769 sedes) debería dar 76.900 Mbps = 76,9 Gbps.
- Suma total de `bw_abast_mbps` ≈ 500.000 Mbps (5000 sedes × 100 Mbps).
- `_cuota_alpha(num_operadores=2, año=8, decisiones=base)` con tipo='rampa' y años_rampa=8 debería dar exactamente α_objetivo (= 0.40 en escenario base).
- `_cuota_alpha(num_operadores=2, año=4, decisiones=base)` con rampa de 8 años debería dar α_objetivo × 0.5 = 0.20.

## Cuando termines

- Reporta los totales territoriales para los 3 escenarios (pesimista/base/optimista) en el año 20.
- Pasa al prompt 04 (`equipment.py`).

# Prompt 05 — Módulo `capex.py`

> Asegúrate de que `equipment.py` está terminado.

Lee `CLAUDE.md` — sección **Decisiones del grupo** (palanca de plan de despliegue) y **Datos de partida** (CAPEX unitarios).

## Objetivo

Calcular la **inversión total y plurianual** del proyecto, distribuyendo el CAPEX a lo largo de los 20 años según el plan de despliegue elegido por el grupo. Salida: matriz CAPEX por categoría × año.

## Componentes del CAPEX

1. **Obra civil de acceso**: km a construir × 100 €/m × 1000 m/km = **100.000 €/km**.
2. **Alta de sedes ABAST**: 20.000 € por sede.
3. **Alta de sedes mayorista**: 20.000 € por sede (cuando se contrata el primer cliente mayorista en ese punto).
4. **Equipos cliente**: 300 € por sede.
5. **Equipos de agregación**: del módulo `equipment.py`.
6. **Equipos troncal**: del módulo `equipment.py`.
7. **Chasis**: 100.000 € por nodo de agregación/troncal.
8. **Datacenter A900**: extra del escenario en `decisiones.yaml`.

## API a exponer

```python
import pandas as pd
import networkx as nx

def deployment_plan(
    g: nx.DiGraph, 
    df_topology: pd.DataFrame,
    decisiones: dict,
) -> pd.DataFrame:
    """Decide qué se despliega en qué año según la estrategia.
    
    Estrategias (decisiones['despliegue']['estrategia']):
        - 'uniforme': repartir uniformemente los 20 años
        - 'priorizado': priorizar los anillos con más sedes/habitantes 
                        primero
        - 'progresivo': empezar con A2 (espina dorsal) y expandir 
                        radialmente; los grandes núcleos al inicio,
                        los pequeños al final
    
    Respeta los topes anuales: km_max_anuales y sedes_max_anuales.
    
    Returns DataFrame indexado por (codigo, año) con columnas:
        km_construido, sedes_abast_conectadas, 
        sedes_mayorista_conectadas, equipos_instalados
    """

def annual_capex(
    deployment_plan_df: pd.DataFrame,
    df_equipment: pd.DataFrame,
    parametros: dict,
    decisiones: dict,
) -> pd.DataFrame:
    """Matriz CAPEX por categoría y por año.
    
    Returns DataFrame con índice = año (1..20) y columnas:
        infraestructura  -- obra civil
        red_activa       -- equipos clientes + agregación + troncal + chasis
        sistemas         -- datacenter A900 + sistemas información (% del CAPEX)
        clientes_mayorista  -- alta nuevos sedes mayorista
        total_anual
    
    El layout debe coincidir con la hoja "Inversion" del Excel template del 
    profesor para poder volcarlo directamente.
    """

def cumulative_capex(annual_capex_df: pd.DataFrame) -> pd.DataFrame:
    """Acumulado de CAPEX a 20 años. Útil para gráficas y para calcular 
    amortización."""
```

## Estrategia de despliegue progresivo (recomendada)

Año 1–3: A2 (espina dorsal) + ciudades grandes (>50.000 hab) + sus accesos críticos. Esto da ingresos rápidos.

Año 4–8: anillos A3, A4, A5, A6, A7 + ciudades medianas (5.000–50.000 hab).

Año 9–15: anillos A8, A9, A10, A11 + accesos menores (1.000–5.000 hab).

Año 16–20: cierre de cobertura + municipios pequeños (<1.000 hab) + redundancias.

Esta estrategia suele dar mejor NPV porque concentra ingresos al inicio.

## Validaciones

- La suma del CAPEX a 20 años debe coincidir con la suma de todos los componentes individuales (obra civil + altas + equipos + datacenter).
- El CAPEX del año 1 debe ser ≥ que el del año 20 (estrategia normal sin redespliegue).
- El total de km construidos a lo largo de los 20 años debe igualar exactamente 4.825 km.
- El total de sedes ABAST conectadas debe igualar 5.000.

## Tests mínimos

- `deployment_plan` con estrategia 'uniforme' reparte 4.825 / 20 ≈ 241 km/año (con redondeos).
- `annual_capex` con escenario base produce una matriz 20×5 de valores positivos.
- Suma total de CAPEX cuadra con `total_capex_equipos` + obra civil + altas + datacenter.

## Cuando termines

- Reportar el CAPEX total y la curva acumulada por año.
- Pasar al prompt 06 (`opex.py`).

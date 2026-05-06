# Prompt 04 — Módulo `equipment.py`

> Asegúrate de que `traffic.py` está terminado.

Lee `CLAUDE.md` — especialmente el paso 5 y 6 del flujo de cálculo, y la frase del profesor *"només ho puc calcular sapiguent el tràfic que passa"*.

## Objetivo

Dos funciones acopladas:

1. **Tráfico acumulado por nodo**: hacer un BFS/DFS desde las hojas del árbol de acceso hacia A900, sumando el tráfico de todos los nodos aguas abajo en cada nodo padre. Esto te da, para cada nodo, el tráfico TOTAL que pasa por él.
2. **Selección de equipo por nodo**: dado el tráfico acumulado y el número de downstream conexiones físicas, elegir el equipo apropiado (10p / 20p / 40p / MPLS / óptico 40λ) según los umbrales de `decisiones.yaml`.

## API a exponer

```python
import networkx as nx
import pandas as pd

def cumulative_traffic(g: nx.DiGraph, df_traffic_per_muni: pd.DataFrame) -> pd.DataFrame:
    """Calcula el tráfico acumulado en cada nodo del grafo.
    
    Algoritmo:
        1. Para cada nodo, inicializar tráfico = tráfico propio del municipio
        2. Recorrer el grafo en orden topológico inverso (hojas → raíz)
        3. En cada nodo, sumar el tráfico de todos los nodos predecesores
           (hijos en el árbol de acceso)
        4. Para los nodos que están en anillos, el tráfico acumulado se
           reparte entre los gateways según la topología (simplificación
           razonable: todo el tráfico del anillo va por el gateway al
           siguiente nivel jerárquico)
    
    Returns DataFrame: codigo, tier, anillos, bw_propio_mbps, 
                       bw_downstream_mbps, bw_acumulado_mbps,
                       n_downstream_links
    
    El bw_acumulado_mbps en A900 debe igualar la suma de TODO el bw del 
    territorio.
    """

def select_equipment(
    df_cumulative: pd.DataFrame, 
    decisiones: dict,
    parametros: dict,
) -> pd.DataFrame:
    """Elige el equipo a desplegar en cada nodo y calcula su coste.
    
    Lógica:
        Para nodos de tier == 'acceso':
            - 1 equipo cliente por sede ABAST → cost = sedes × 300 €
        
        Para nodos de tier == 'agregacion':
            - 1 chasis (100k €) + N cajas de agregación según downstream_links
            - Eleccion según umbrales de decisiones['equipos']:
                * downstream <= umbral_10p_a_20p → 10p (1.5k €)
                * <= umbral_20p_a_40p → 20p (5k €)
                * <= umbral_40p_a_mpls → 40p (12k €)
                * > umbral → varias 40p en paralelo + MPLS troncal
            - Si bw_acumulado > capacidad de la opción elegida, escalar al siguiente
        
        Para nodos de tier == 'troncal':
            - 1 chasis (100k €) + 1 MPLS (50k €) + 1 óptico 40λ (60k €)
            - A900 (datacenter) además incluye datacenter_a900.capex_extra 
              de decisiones.yaml
    
    Returns DataFrame: codigo, tier, equipo_principal, n_unidades, 
                       capex_equipo, capex_chasis, capex_total_nodo
    """

def total_capex_equipos(df_equipment: pd.DataFrame) -> dict:
    """Resumen global del CAPEX de equipos.
    
    Returns: {
        'equipo_cliente': total_eur,
        'equipo_agregacion': total_eur,
        'equipo_troncal': total_eur,
        'chasis': total_eur,
        'datacenter_a900': total_eur,
        'total': total_eur,
    }
    """
```

## Sanity check de capacidad de los equipos

Recordar las capacidades nominales:

- 10 puertos × 1 Gbps = **10 Gbps** agregados máximo
- 20 puertos × 1 Gbps = **20 Gbps**
- 40 puertos × 1 Gbps = **40 Gbps**
- MPLS troncal = típicamente 100+ Gbps
- Óptico 40λ = 40 lambdas × 10 Gbps = **400 Gbps**

Si en un nodo `bw_acumulado_mbps > capacidad_nominal_mbps` del equipo elegido por umbrales, escalar al siguiente y avisar con un warning del tipo *"Nodo A800: tráfico 12.5 Gbps excede capacidad 10 Gbps, escalando a 20p"*.

## Validaciones

- El tráfico acumulado en A900 debe ser ≥ que en cualquier otro nodo.
- La suma de `n_downstream_links` para todos los nodos de agregación debe ser ≥ 5000 (las 5000 sedes ABAST tienen que terminar en algún equipo cliente).
- Reportar el coste total de equipos por categoría — debería estar en el orden de **decenas a centenas de millones de euros**.

## Tests mínimos

- `cumulative_traffic` aplicado a un grafo de 5 nodos lineal (A→B→C→D→E) con tráfico [10,20,30,40,50] propio en cada uno debe dar acumulado [10,30,60,100,150] respectivamente.
- Tráfico acumulado en A900 ≈ tráfico total del territorio (ABAST + mayorista).
- `select_equipment` para un nodo con 50 downstream links debe escalar a múltiples 40p o MPLS (no quedarse en 10p).

## Cuando termines

- Pasa al prompt 05 (`capex.py`).

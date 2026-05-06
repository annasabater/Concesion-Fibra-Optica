# Prompt 02 — Módulo `topology.py`

> Este es el módulo que entregas mañana. Asegúrate de que `load.py` está limpio y los tests pasan antes de empezar.

Lee `CLAUDE.md` para entender la arquitectura de la red en 3 capas (troncal / agregación / acceso), los anillos, A900 como datacenter central, y la estructura del árbol de acceso multi-hop.

## Objetivo del módulo

Construir el grafo NetworkX que representa la topología completa de la red, con A900 como raíz lógica. El grafo debe permitir:

- Recorrer el árbol de acceso desde cualquier nodo hacia A900 y al revés
- Identificar a qué anillo de agregación pertenece cualquier municipio (incluso de acceso, vía cadena de hops)
- Calcular kilómetros totales por anillo y por capa
- Servir de base para los módulos de tráfico, equipos y visualización
- Generar dos vistas gráficas: **anillos limpios** (sólo troncal+agregación) y **topología completa** (todos los 900 municipios)

## API a exponer

```python
import networkx as nx
import pandas as pd

def build_graph(df_topology: pd.DataFrame) -> nx.DiGraph:
    """Construye el grafo dirigido de la red completa.
    
    El grafo es DIRIGIDO con la convención: las aristas apuntan desde 
    el municipio hijo hacia su padre (es decir, hacia A900). Esto facilita
    el cálculo de tráfico acumulado (BFS desde hojas).
    
    Atributos de nodo:
        - tier: 'acceso' | 'agregacion' | 'troncal'
        - hab: int
        - sedes_abast: int
        - num_operadores: int
        - anillos_agregacion: set[str]  # {'A1'} o {'A1','A2'} para A900
        - anillos_troncal: set[str]     # {'T1'} o {'T1','T2','T3'} para A900
    
    Atributos de arista (origen → destino):
        - km: float
        - tipo: 'acceso' (solo para enlaces de la capa de acceso)
    
    Para los anillos (agregación y troncal), añadir aristas extra que 
    representen la conexión circular entre nodos consecutivos del mismo 
    anillo. Estas aristas tienen tipo 'anillo_agregacion' o 'anillo_troncal'
    y NO contribuyen al árbol jerárquico — son sólo para visualización 
    de redundancia.
    """

def get_root(g: nx.DiGraph) -> str:
    """Devuelve el código del nodo raíz (A900)."""

def get_downstream_nodes(g: nx.DiGraph, node: str) -> set[str]:
    """Devuelve todos los nodos que cuelgan aguas abajo del nodo dado 
    (vía aristas de tipo 'acceso')."""

def resolve_aggregation_ring(g: nx.DiGraph, node: str) -> set[str]:
    """Resuelve a qué anillo(s) de agregación pertenece un municipio, 
    siguiendo la cadena de acceso hasta encontrar un nodo de agregación.
    
    Para nodos de agregación devuelve directamente sus anillos_agregacion.
    Para nodos de acceso recorre el padre hasta encontrar un nodo con 
    tier in {'agregacion', 'troncal'}.
    """

def stats_by_ring(g: nx.DiGraph) -> pd.DataFrame:
    """Tabla resumen por anillo con columnas:
        anillo, tipo (troncal|agregacion), n_nodos, n_munis_cubiertos,
        n_sedes_abast, total_hab, km_existing, km_acceso_construido
    
    Esta es la matriz que el profe pidió en clase (filas T1, T2, T3, A1..A11).
    """
```

## Algoritmo clave: resolver anillo de un municipio de acceso

Los municipios de acceso (codigo 1–799) NO tienen anillo asignado en el Excel. Hay que resolverlo siguiendo la cadena `destino_acceso → destino_acceso → ...` hasta llegar a un nodo de agregación. **Cuidado con los ciclos** (no debería haberlos, pero limita iteraciones a 20).

```python
def _walk_to_aggregation(g, start, max_hops=20):
    cur = start
    seen = set()
    while cur not in seen and len(seen) < max_hops:
        if g.nodes[cur]['tier'] != 'acceso':
            return g.nodes[cur]['anillos_agregacion']
        seen.add(cur)
        successors = list(g.successors(cur))
        if not successors:
            return set()
        cur = successors[0]
    return set()
```

## Gotcha distribucional importante

Del análisis previo, **casi 793 de los 900 municipios resuelven al anillo A2** (porque la cadena de destino de la mayoría termina en A800–A807, todos en A2). Esto es deliberado del profesor; no es un error. Tu tabla `stats_by_ring` debe reflejar este desbalance honestamente — A2 va a aparecer con ~2.214 sedes y ~4.735 km de acceso, mientras que A8–A11 tendrán cifras pequeñas (sólo las sedes de los nodos de agregación que les pertenecen).

## Visualización (función incluida en este módulo, vista preliminar — la versión final va en `visualize.py`)

```python
def draw_rings_only(g: nx.DiGraph, output_path: Path) -> None:
    """Dibuja sólo la capa troncal + agregación con A900 al centro,
    los 3 anillos troncales en forma de pétalo, y los 11 anillos de
    agregación colgando de sus gateways. Layout MANUAL (no spring_layout)."""

def draw_full_topology(g: nx.DiGraph, output_path: Path) -> None:
    """Dibuja la topología completa con los 900 municipios. Acceso en
    pequeño, agregación más grande, troncal y A900 destacados.
    Layout: agregación en flor + accesos en hojas radiales."""
```

**Importante para el layout en flor**:

- A900 al centro: `pos['A900'] = (0, 0)`
- Los 3 anillos troncales como elipses alrededor de A900, separadas 120° entre sí
- Cada anillo de agregación cuelga de su gateway (A899→A3 abajo de T1, A892→A10 al lado, etc.)
- Para el dibujo completo, usar layout radial sobre cada agregación (los accesos colgando como rayos)

NO uses `nx.spring_layout` — el grafo del otro grupo del año pasado usaba spring_layout y el resultado era ilegible. Calcula posiciones manualmente con trigonometría.

## Tests mínimos en `tests/test_topology.py`

- `build_graph` produce un grafo con 900 nodos y al menos 900 aristas (799 acceso + 91 anillo agregación + 10 anillo troncal + las cíclicas dentro de los anillos).
- `get_root` devuelve `'A900'`.
- `resolve_aggregation_ring('A1')` devuelve un set que incluye `'A2'`.
- `stats_by_ring` produce 14 filas (3 troncal + 11 agregación) y los totales cuadran con los del Excel.

## Cuando termines

- Genera las dos imágenes PNG en `outputs/escenario_base/topologia_anillos.png` y `topologia_completa.png`.
- Reporta el total de nodos, aristas, y la tabla `stats_by_ring`.
- Esa tabla + el PNG de "anillos limpios" es lo que entregas mañana al profesor.

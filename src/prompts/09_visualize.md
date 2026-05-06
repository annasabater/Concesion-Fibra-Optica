# Prompt 09 — Módulo `visualize.py`

> Asegúrate de que `topology.py` y `pnl.py` están terminados.

Lee `CLAUDE.md` — sección **Topología de la red** (la flor de pétalos con A900 al centro).

## Objetivo

Generar todas las **imágenes y gráficas** que se incluyen en la oferta técnica y económica. Producción profesional, lista para meter en PDF de oferta.

## Funciones a exponer

```python
import networkx as nx
import pandas as pd
from pathlib import Path

# === TOPOLOGÍA ===

def draw_rings_only(g: nx.DiGraph, output_path: Path) -> None:
    """Topología lógica: A900 al centro, 3 anillos troncales como pétalos
    a 120° entre sí, 11 anillos de agregación colgando de sus gateways.
    
    Layout MANUAL (NO spring_layout):
        - A900 en (0, 0), radio grande
        - T1 ellipse cx=(2.5, 0), T2 cx=(-1.25, 2.16), T3 cx=(-1.25, -2.16)
        - Cada anillo de agregación posicionado adyacente a su gateway
        - Anotar cada nodo con su código y nº de sedes
    
    Estilo: minimalista, fondo blanco, líneas finas, colores distinguibles
    para troncal/agregación/A900. Output PNG 300dpi y SVG.
    """

def draw_full_topology(g: nx.DiGraph, output_path: Path) -> None:
    """Topología completa con los 900 municipios.
    
    Layout: agregación en flor + accesos como ramas radiales.
    Los nodos de acceso pequeños (gris claro), agregación medianos 
    (azul), troncal grandes (rojo), A900 destacado.
    Tamaño del nodo proporcional a habitantes.
    """

def draw_ring_detail(g: nx.DiGraph, ring_id: str, output_path: Path) -> None:
    """Vista de detalle de un anillo de agregación concreto (ej. 'A2'),
    mostrando todos sus nodos + el árbol de acceso colgando.
    Útil para anexos de la oferta técnica."""

# === FINANCIERO ===

def plot_capex_by_year(capex_df: pd.DataFrame, output_path: Path) -> None:
    """Barras apiladas: CAPEX por año por categoría 
    (infraestructura, red activa, sistemas, mayorista).
    20 barras, eje Y en M€."""

def plot_revenue_vs_costs(
    revenue_df: pd.DataFrame, 
    opex_df: pd.DataFrame, 
    output_path: Path,
) -> None:
    """Líneas: ingresos totales vs costes totales a 20 años.
    Sombrear el área entre ambas (EBITDA).
    Marcar el año de break-even."""

def plot_cash_flow(
    income_df: pd.DataFrame, 
    output_path: Path,
) -> None:
    """Cash flow anual (barras) + CF acumulado (línea sobre eje secundario).
    Marcar payback period con línea vertical."""

def plot_scenario_comparison(
    kpis_base: dict,
    kpis_optimista: dict,
    kpis_pesimista: dict,
    output_path: Path,
) -> None:
    """Tabla comparativa de los 3 escenarios. NPV / IRR / Payback / EBITDA.
    Útil para defender la robustez ante reequilibrio económico."""

def plot_traffic_heatmap(
    df_cumulative: pd.DataFrame, 
    g: nx.DiGraph, 
    output_path: Path,
) -> None:
    """Mapa de calor del tráfico acumulado en cada nodo del grafo.
    Color = bw_acumulado_mbps en escala log."""
```

## Reglas de estilo

- **Sin colorines de matplotlib por defecto**. Paleta corporativa: rojo carmín para troncal, azul oscuro para agregación, verde apagado para acceso, naranja para A900. Negro para texto, gris claro para grids.
- **Tipografía**: sans-serif, tamaño legible (no microscópico). En diagramas de topología, etiquetas sólo para nodos importantes (A900, los 9 gateways, los anillos).
- **Tamaño**: figuras grandes (16×10 inches), DPI=300, formato PNG y SVG (PNG para presentación, SVG para escalable en oferta).
- **Sin gridlines** salvo en los gráficos financieros (donde sí ayudan a leer).
- **Leyenda** clara y siempre fuera del área del gráfico.
- **Titulo**: cada figura tiene título descriptivo en una sola línea, sin tecnicismos innecesarios.

## Validación visual

Antes de dar por bueno:

1. La topología debe verse "como una flor" — A900 al centro, 3 pétalos troncales perfectamente visibles.
2. El gráfico de cash flow debe tener un valle claro al inicio (CAPEX) y recuperación (ingresos).
3. La comparativa de escenarios debe distinguirse visualmente (3 colores distintos).
4. Cualquier anotación numérica debe formatearse con separadores de miles y unidades (`60.000.000 €` o `60 M€`, no `60000000`).

## Cuando termines

- Genera todas las imágenes en `outputs/escenario_base/img/` y reporta cuáles se han creado.
- Pasa al prompt 10 (`report.py`).

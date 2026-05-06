# Prompt 10 — Módulo `report.py`

> Asegúrate de que todos los módulos anteriores producen los DataFrames esperados.

Lee `CLAUDE.md` — sección **Datos de partida** (las hojas vacías del Excel template) y **Filosofía de trabajo**.

## Objetivo

Producir los **outputs físicos** que se entregan al profesor y a la administración:

1. **Excel completo** rellenando las hojas vacías del template original (Plan despliegue, Inversion, Costes, Ingresos, Cuenta de resultados).
2. **PDF de oferta técnica** (≤30 páginas) con topología, dimensionado, equipos, plan de despliegue, garantías SLA.
3. **PDF de oferta económica** (≤20 páginas) con CAPEX, OPEX, ingresos, cuenta de resultados, KPIs, escenarios.
4. **Resumen ejecutivo** (1 página) con los KPIs y un párrafo de defensa.

## API a exponer

```python
from pathlib import Path
import pandas as pd

def fill_excel_template(
    template_path: Path,
    output_path: Path,
    deployment_plan_df: pd.DataFrame,
    capex_df: pd.DataFrame,
    opex_df: pd.DataFrame,
    revenue_df: pd.DataFrame,
    income_df: pd.DataFrame,
) -> None:
    """Carga el Excel template del profesor, rellena las hojas vacías 
    sin destruir las que tienen datos, y guarda el resultado.
    
    Hojas a rellenar (todas con índice de años en la fila 1):
        Plan despliegue
        Inversion
        Costes
        Ingresos
        Cuenta de resultados
    
    Usar openpyxl con load_workbook + ws.cell(row, col, value=...) para 
    no perder fórmulas existentes.
    """

def generate_oferta_tecnica_pdf(
    output_path: Path,
    g: nx.DiGraph,
    df_topology: pd.DataFrame,
    df_equipment: pd.DataFrame,
    deployment_plan_df: pd.DataFrame,
    decisiones: dict,
    img_dir: Path,
) -> None:
    """Genera el PDF de oferta técnica.
    
    Estructura sugerida:
        1. Resumen ejecutivo (1 pág)
        2. Comprensión del proyecto y contexto LCSP (2 pág)
        3. Topología de la red — diagrama lógico + por anillo (3 pág)
        4. Dimensionado de tráfico — ABAST + mayorista (3 pág)
        5. Selección de equipos por anillo + tabla resumen (4 pág)
        6. Plan de despliegue plurianual (3 pág)
        7. Garantías de servicio: redundancia, SLA, OAM, GIS (3 pág)
        8. Cumplimiento normativo (RGPD, ENS, accesibilidad) (2 pág)
        9. Equipo profesional y experiencia (2 pág)
        10. Anexos técnicos (3 pág)
    
    Usar reportlab con plantilla institucional sobria. Insertar las imágenes 
    generadas en el módulo visualize.py.
    """

def generate_oferta_economica_pdf(
    output_path: Path,
    revenue_df: pd.DataFrame,
    opex_df: pd.DataFrame,
    capex_df: pd.DataFrame,
    income_df: pd.DataFrame,
    kpis_dict: dict,
    kpis_3escenarios: dict,
    img_dir: Path,
) -> None:
    """Genera el PDF de oferta económica con el modelo financiero a 20 años.
    
    Estructura:
        1. Modelo de negocio (1 pág)
        2. Hipótesis y decisiones del grupo (2 pág)
        3. Plan de inversiones (CAPEX) (3 pág)
        4. Costes operativos (OPEX) (2 pág)
        5. Modelo de ingresos (3 pág)
        6. Cuenta de resultados a 20 años + KPIs (3 pág)
        7. Análisis de escenarios y sensibilidad (3 pág)
        8. Tarifas propuestas (1 pág)
        9. Reequilibrio económico — propuesta (2 pág)
    """

def generate_executive_summary(
    output_path: Path,
    kpis: dict,
    decisiones: dict,
) -> None:
    """Resumen ejecutivo de 1 página con los KPIs principales y un 
    párrafo de defensa de la oferta. Útil como portada de las dos PDFs."""
```

## Convenciones de presentación PDF

- **Plantilla sobria**: header con logo (placeholder), tipografía serif para texto, sans-serif para tablas/títulos.
- **Numeración** de páginas y secciones desde el principio.
- **Tablas formateadas** con líneas finas, alternancia de filas, totales en negrita.
- **Imágenes** centradas con pie de figura numerado.
- **Anexos** al final con datos detallados (tablas por anillo, CAPEX desglosado, etc.).

## Validación

Antes de considerar un PDF "entregable":

- Render correcto en lector estándar (Adobe / Preview / lector navegador).
- Sin errores ortográficos básicos (pasar por un corrector — el grupo es responsable, no Claude).
- Cada figura tiene su pie + número.
- Cada cifra tiene unidades y formato (separador de miles, decimales razonables).
- Sumas de tablas cuadran con totales.
- Trazabilidad: cualquier número del PDF se puede localizar en el Excel.

## Cuando termines

- Genera los 3 outputs (Excel + 2 PDFs + resumen) para el escenario base.
- Reporta tamaño de archivo y nº de páginas de cada PDF.
- Pasa al prompt 11 (`main.py` — orquestador).

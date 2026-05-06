# Prompt 08 — Módulo `pnl.py`

> Asegúrate de que `revenue.py`, `opex.py` y `capex.py` están terminados.

Lee `CLAUDE.md` — sección **Restricciones contractuales clave** (reequilibrio económico) y **Filosofía de trabajo** (3 escenarios siempre).

## Objetivo

Construir la **cuenta de resultados a 20 años** y los **KPIs financieros** que se defienden en la oferta económica. Este es el módulo que vende el proyecto al tribunal.

## Estructura de la cuenta de resultados

```
Año                           1    2    3   ... 20
─────────────────────────────────────────────────
Ingresos                      X    X    X       X
Costes operativos (OPEX)      X    X    X       X
─────────────────────────────────────────────────
EBITDA                        X    X    X       X
Amortización (CAPEX/años)     X    X    X       X
─────────────────────────────────────────────────
EBIT                          X    X    X       X
Resultado antes impuestos     X    X    X       X
Impuesto sociedades (25%)     X    X    X       X
─────────────────────────────────────────────────
Resultado neto                X    X    X       X

Cash flow libre (CF)          X    X    X       X
CF acumulado                  X    X    X       X
```

## API a exponer

```python
import pandas as pd
import numpy_financial as npf

def income_statement(
    revenue_df: pd.DataFrame,
    opex_df: pd.DataFrame,
    capex_df: pd.DataFrame,
    decisiones: dict,
) -> pd.DataFrame:
    """Cuenta de resultados completa a 20 años.
    
    Returns DataFrame indexado por año (1..20) con las filas listadas arriba.
    Compatible con la hoja "Cuenta de resultados" del Excel template.
    """

def free_cash_flow(income_df: pd.DataFrame, capex_df: pd.DataFrame) -> pd.Series:
    """Cash flow libre por año = EBITDA - CAPEX_año - impuestos."""

def kpis(
    income_df: pd.DataFrame, 
    capex_df: pd.DataFrame, 
    decisiones: dict,
) -> dict:
    """KPIs financieros que vas a defender en la oferta:
    
    Returns: {
        'capex_total': float,
        'opex_total_20años': float,
        'ingresos_total_20años': float,
        'ebitda_total_20años': float,
        'ebitda_margin_estacionario': float,  # EBITDA/Ingresos en año 20
        'npv': float,        # Net Present Value descontado a tasa decisiones['descuento']['tasa']
        'irr': float,        # Internal Rate of Return
        'payback_years': float,  # Año en que CF acumulado pasa de negativo a positivo
        'cash_flow_minimo': float,  # punto más bajo del CF acumulado (cuánto financiamiento se necesita)
        'roi_20años': float,  # (resultado_acumulado / capex_total) en %
    }
    """

def sensitivity_analysis(
    base_inputs: dict,
    parameter_ranges: dict,
) -> pd.DataFrame:
    """Análisis de sensibilidad: variar cada palanca ±X% y ver impacto en NPV.
    
    Útil para la defensa del reequilibrio económico — demuestras que tu plan
    es robusto a desviaciones moderadas.
    """
```

## Política de amortización

Lineal a 20 años (vida útil de la concesión) para todo el CAPEX. Es lo más simple y defendible. Si quieres sofisticar:

- Obra civil: amortización a 30 años (pero como la concesión es de 20, se amortiza a 20).
- Equipos activos: amortización a 8 años (vida útil técnica). Habría que reinvertir hacia el año 8–10 para reemplazar equipos. Esto es un sobre-coste que pesa en el CAPEX del segundo decenio.
- Sistemas de información: amortización a 5 años.

Para simplicidad, en la primera versión usa amortización lineal a 20 años para todo y deja una nota de mejora para el TFM.

## KPIs objetivo defendibles

Para una concesión de 20 años de fibra pública, los KPIs razonables son:

- **NPV** (con tasa 6%): positivo (>10% del CAPEX total).
- **IRR**: 8–12% (tasa que un inversor privado esperaría para este tipo de infraestructura).
- **Payback**: 8–12 años. Si > 15 años, el proyecto pinta mal.
- **EBITDA margin** estacionario: 30–50% (lo típico en operadores de fibra).

Si tu modelo da números fuera de estos rangos en el escenario base, hay un parámetro mal calibrado.

## Validaciones

- `npv` debe ser positivo en escenario base y optimista. En pesimista puede ser ligeramente positivo o negativo — eso es lo que justifica pedir reequilibrio si el escenario pesimista se materializa.
- La diferencia de NPV entre escenarios optimista y pesimista te da el "ancho" del riesgo — usar para defensa.

## Tests mínimos

- Para una pequeña simulación con CAPEX=100, ingresos=20 y opex=10 cada año, verificar manualmente NPV, IRR, payback.
- El payback NO puede ser negativo o NaN — si todos los CF son positivos desde el año 1 (raro), payback = 0.

## Cuando termines

- Reporta los KPIs de los 3 escenarios en una tabla.
- Pasa al prompt 09 (`visualize.py`).

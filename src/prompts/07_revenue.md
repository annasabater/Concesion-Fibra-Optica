# Prompt 07 — Módulo `revenue.py`

> Asegúrate de que `traffic.py` y `capex.py` están terminados (necesitas saber qué se conecta cada año).

Lee `CLAUDE.md` — sección **Modelo de negocio** y **Datos de partida** (tarifas).

## Objetivo

Calcular los **ingresos plurianuales** de las dos fuentes (ABAST + mayorista) año a año, alineados con el ritmo de despliegue (una sede sólo genera ingresos cuando está conectada e iluminada).

## Lógica de ingresos

### ABAST (autoprestación)

- Ingreso recurrente: 1.000 €/mes/sede × 12 = **12.000 €/año por sede activa**.
- Alta: 0 €.
- Una sede genera ingreso desde el momento en que se conecta hasta el final del horizonte.

### Mayorista

- Alta: 1.500 € por sede mayorista (one-shot el año en que se conecta).
- Recurrente: 700 €/mes/sede mayorista × 12 = **8.400 €/año por sede activa**.
- El número de sedes mayorista por municipio depende de:
    - Número de operadores presentes (`num_operadores` del Excel)
    - Cuota α capturada por nosotros (palanca del escenario)
    - Tiempo (rampa α(t))

## API a exponer

```python
import pandas as pd

def annual_revenue(
    deployment_plan_df: pd.DataFrame,
    df_topology: pd.DataFrame,
    parametros: dict,
    decisiones: dict,
) -> pd.DataFrame:
    """Matriz de ingresos por categoría y por año.
    
    Returns DataFrame con índice = año (1..20) y columnas:
        sedes_abast_activas  -- nº de sedes acumuladas
        clientes_mayorista_activos
        ingresos_abast       -- recurrente del año
        ingresos_mayorista   -- recurrente + altas del año
        ingresos_total
    
    El layout debe coincidir con la hoja "Ingresos" del Excel template.
    """

def revenue_per_municipality(
    df_topology: pd.DataFrame,
    parametros: dict,
    decisiones: dict,
    año: int,
) -> pd.DataFrame:
    """Detalle de ingresos por municipio en un año concreto. 
    Útil para análisis de sensibilidad y para generar tablas por anillo."""
```

## Modelo de adopción mayorista (rampa)

```python
def _clientes_mayorista_año(num_operadores, hab, año, decisiones):
    hogares = hab / decisiones['mayorista']['habitantes_por_hogar']
    
    cuota_obj = decisiones['mayorista']['cuota_mercado']['alpha_objetivo']
    años_rampa = decisiones['mayorista']['cuota_mercado']['años_rampa']
    tipo = decisiones['mayorista']['cuota_mercado']['tipo']
    
    if tipo == 'rampa':
        cuota = cuota_obj * min(año / años_rampa, 1.0)
    elif tipo == 'equilibrio':
        cuota = 1 / (num_operadores + 1)
    elif tipo == 'agresivo':
        cuota = 1 / num_operadores
    
    return hogares * cuota
```

## Validaciones

- En régimen estacionario, `ingresos_abast` total = 5.000 sedes × 12.000 €/año = **60 M€/año**.
- Los `ingresos_mayorista` en escenario base deben rondar 50–150 M€/año en estacionario, dependiendo de α y los hogares totales.
- Los ingresos del año 1 deben ser bajos (red apenas activa).
- La curva debe crecer y estabilizarse antes del año `años_rampa`.

## Tests mínimos

- `annual_revenue` con `años_rampa=8` y `alpha_objetivo=0.4` debe alcanzar la cuota plena en el año 8.
- Suma de `ingresos_abast` a lo largo de 20 años con todas las sedes activas desde el año 1 = 5.000 × 12.000 × 20 = 1.200 M€.
- En el año 1 con escenario 'progresivo', sólo las sedes de las ciudades grandes están conectadas — verificar que `ingresos_abast_año1 << ingresos_abast_año10`.

## Cuando termines

- Pasa al prompt 08 (`pnl.py`) — el corazón económico.

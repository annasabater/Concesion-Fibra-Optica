# Prompt 06 — Módulo `opex.py`

> Asegúrate de que `capex.py` está terminado.

Lee `CLAUDE.md` — sección **Datos de partida** (parámetros OPEX).

## Objetivo

Calcular los **costes operativos plurianuales** que escalan con la red activa. A diferencia del CAPEX (inversión puntual), el OPEX es recurrente y crece año a año a medida que se va activando red.

## Componentes del OPEX

1. **RRHH**: a estimar. Sugerencia: 1 empleado por cada 200 km de red activa + 5 empleados base de NOC + 10 empleados administración. Salario medio defendible 50.000 €/año (incluida cuota patronal). Es una palanca que el grupo decide.
2. **Mantenimiento de infraestructura**: 250 €/km·año × km de red activa.
3. **Mantenimiento de equipos activos**: 10% del CAPEX acumulado en red_activa.
4. **Mantenimiento de sistemas información**: 10% del CAPEX acumulado en sistemas.
5. **Derechos de paso e impuestos**: 3% de los ingresos del año.
6. **Costes de ventas mayorista**: 10% sobre los ingresos mayorista del año.
7. **Gastos generales y otros**: 700.000 €/año (fijo).
8. **OPEX extra del datacenter A900**: del escenario en `decisiones.yaml`.

## API a exponer

```python
import pandas as pd

def annual_opex(
    annual_capex_df: pd.DataFrame, 
    deployment_plan_df: pd.DataFrame,
    revenue_df: pd.DataFrame,
    parametros: dict,
    decisiones: dict,
) -> pd.DataFrame:
    """Matriz OPEX por categoría y por año.
    
    Returns DataFrame con índice = año (1..20) y columnas:
        rrhh
        mant_infraestructura
        mant_equipos
        mant_sistemas
        derechos_uso
        costes_ventas
        gastos_generales
        opex_datacenter
        total_anual
    
    El layout debe coincidir con la hoja "Costes" del Excel template del 
    profesor para poder volcarlo directamente.
    
    Importante: necesita revenue_df (del módulo revenue.py) para los 
    componentes que dependen de ingresos. La pipeline en main.py debe 
    calcular revenue ANTES que opex, o iterar 2 veces.
    """
```

## Lógica de "red activa por año"

El mantenimiento se paga sobre la red ACTIVA (ya construida y en operación), no sobre la red planificada. Por tanto:

- Año `n`: mantenimiento = `f(km_acumulados_hasta_año_n, capex_acumulado_red_activa_hasta_año_n)`.
- Esto crea una curva creciente que se estabiliza a partir del año en que se completa el despliegue.

## Validaciones

- El OPEX del año 1 debe ser bajo (red apenas activa) y crecer hasta estabilizarse.
- El OPEX en régimen estacionario (último año del horizonte) debe ser del orden de **50–100 M€/año** (5000 sedes activas, mantenimiento, RRHH, generales).
- `derechos_uso` y `costes_ventas` se calculan a partir de los ingresos del año. Si revenue_df no está disponible aún, devolver 0 en esas columnas y permitir un segundo pase.

## Tests mínimos

- `annual_opex` con todos los inputs en cero debe dar exactamente `gastos_generales` (700k €) por año.
- En régimen estacionario, `mant_infraestructura` debe ser ≈ 250 € × 7.825 km = 1.95 M€/año.

## Cuando termines

- Pasa al prompt 07 (`revenue.py`).

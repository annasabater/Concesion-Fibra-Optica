# Prompt 01 — Módulo `load.py`

> Asegúrate de haber ejecutado el prompt 00 y de que la estructura del proyecto está creada.

Lee `CLAUDE.md` para el contexto. Especialmente la sección de **datos de partida**, donde se describen las columnas del Excel y los gotchas (fórmulas en filas 800–900, cargar con `data_only=True`).

## Objetivo del módulo

Cargar y normalizar los archivos de entrada (`Despliegue de REd Municipios 2026.xlsx`, `parametros_economicos.xlsx`, `decisiones.yaml`). Devolver estructuras de datos limpias, validadas y tipadas. Es la única capa que toca disco — el resto del proyecto trabaja con DataFrames y dicts en memoria.

## API a exponer

```python
from pathlib import Path
import pandas as pd

def load_topology(path: Path) -> pd.DataFrame:
    """Carga la hoja 'Municipios y topologia de red' del Excel.
    
    Args:
        path: ruta al archivo Despliegue de REd Municipios 2026.xlsx
    
    Returns:
        DataFrame con columnas:
            codigo (int), hab (int), sedes_abast (int), num_operadores (int),
            municipio (str), destino_acceso (str | None), km (float),
            anillo_agregacion (str | None), anillo_troncal (str | None),
            tier (str: 'acceso' | 'agregacion' | 'troncal').
    
    El campo `tier` se calcula:
        - si anillo_troncal != NA → 'troncal'
        - elif anillo_agregacion != NA → 'agregacion'
        - else → 'acceso'
    
    Para los nodos de agregación/troncal (códigos 800-900), el campo 
    destino_acceso del Excel contiene FÓRMULAS que pueden devolver valores 
    extraños. Como esos nodos son terminadores del árbol, se normaliza el 
    destino_acceso a None para esas filas.
    """

def load_parameters(path: Path) -> dict:
    """Carga la hoja 'Parámetros' a un dict anidado por categoría.
    
    Returns: {
        'ingresos': {
            'alta_abast': 0,
            'recurrente_abast': 1000,
            'alta_mayorista': 1500,
            'recurrente_mayorista': 700,
        },
        'opex': {
            'mant_fibra_eur_km_año': 250,
            'mant_equipos_pct_capex': 0.10,
            'mant_si_pct_capex': 0.10,
            'derechos_paso_pct_ingresos': 0.03,
            'costes_ventas_mayorista_pct': 0.10,
            'gastos_generales_anuales': 700000,
        },
        'capex': {
            'alta_sede_abast': 20000,
            'alta_sede_mayorista': 20000,
            'obra_civil_urbana_eur_m': 100,
            'obra_civil_acceso_eur_m': 100,
            'nodo_chasis': 100000,
            'equipo_cliente': 300,
            'equipo_agreg_10p': 1500,
            'equipo_agreg_20p': 5000,
            'equipo_agreg_40p': 12000,
            'equipo_troncal_mpls': 50000,
            'equipo_troncal_optico_40l': 60000,
        },
    }
    """

def load_decisiones(path: Path, escenario: str = "base") -> dict:
    """Carga decisiones.yaml y devuelve el escenario solicitado, fusionando con 'base'.
    
    Si escenario != 'base', hace deep merge con la configuración de 'base'
    para que los escenarios optimista/pesimista hereden los valores no 
    sobreescritos.
    
    Raises:
        ValueError si el escenario no existe.
    """
```

## Validaciones a implementar

- `codigo` debe ser único y cubrir el rango 1–900.
- `hab`, `sedes_abast` deben ser enteros no negativos.
- `num_operadores` entre 1 y 5.
- `km` debe ser número no negativo (puede ser 0 para nodos raíz).
- Los nombres de anillo, si están presentes, deben coincidir con `T1|T2|T3` o `A1..A11` (admitir el caso especial `A1, A2` y `T1, T2,T3` con espacios variables — limpiarlo a una lista normalizada o a `set`).
- Lanzar warning si alguna fila de acceso (tier == 'acceso') tiene `destino_acceso` en None — eso indicaría un agujero en el árbol.

## Manejo de la peculiaridad del Excel

- Cargar con `openpyxl` y `data_only=True` para que las fórmulas se resuelvan a valores. Si data_only no devuelve nada (Excel sin recalcular), usar pandas con `pd.read_excel(..., engine="openpyxl")`.
- Los nombres de columna del Excel real tienen tildes y espacios (ej. `Anillo agregación ` con espacio final). Normalizarlos a snake_case sin tildes en el DataFrame de salida.
- La hoja tiene 2 filas de cabecera (la primera con el agrupador "Acceso" mergeado, la segunda con los nombres). Usar `header=3` o equivalente, o detectar la fila de cabeceras buscando 'Código'.

## Tests mínimos en `tests/test_load.py`

- Cargar el Excel real y verificar 900 filas, columnas esperadas, tipos correctos.
- Verificar que `codigo` cubre 1–900 sin huecos.
- Verificar que la suma de `sedes_abast` da 5000.
- Verificar que la suma de `hab` da 8.590.900.
- Verificar que hay exactamente 799 filas con tier='acceso', 91 con 'agregacion', 10 con 'troncal'.
- Cargar `decisiones.yaml` con escenario='base' y verificar que devuelve un dict con la estructura esperada.

## Cuando termines

- Implementa, ejecuta los tests, asegúrate de que pasan.
- Reporta cualquier sorpresa de los datos (filas con NaN inesperados, valores fuera de rango, etc.).
- No avances al prompt 02 hasta que `load.py` esté pulido.

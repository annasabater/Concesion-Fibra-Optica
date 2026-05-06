# Prompt 11 — Módulo `main.py` (orquestador)

> Asegúrate de que TODOS los módulos anteriores funcionan independientemente.

## Objetivo

Construir el **orquestador end-to-end** que ejecuta toda la pipeline para un escenario dado y deja los outputs listos en `outputs/escenario_<nombre>/`. Una invocación = una ejecución completa, idempotente, con logging claro.

## Comportamiento esperado

```bash
python main.py --escenario base
python main.py --escenario optimista
python main.py --escenario pesimista
python main.py --todos    # ejecuta los 3 secuencialmente
```

Cada ejecución:

1. Carga datos (`load.py`).
2. Construye topología (`topology.py`) y genera diagramas básicos.
3. Calcula tráfico ABAST + mayorista por municipio (`traffic.py`).
4. Calcula tráfico acumulado y selección de equipos (`equipment.py`).
5. Decide el plan de despliegue plurianual y calcula CAPEX (`capex.py`).
6. Calcula ingresos plurianual (`revenue.py`).
7. Calcula OPEX plurianual (`opex.py`) — necesita revenue para los % sobre ingresos.
8. Construye cuenta de resultados y KPIs (`pnl.py`).
9. Genera todas las imágenes (`visualize.py`).
10. Rellena Excel template y genera PDFs (`report.py`).

## API y CLI

```python
from pathlib import Path
import argparse
import logging

def main(escenario: str, data_dir: Path, output_dir: Path) -> dict:
    """Pipeline completo para un escenario.
    
    Returns dict de KPIs del escenario para que pueda invocarse 
    programáticamente y comparar escenarios.
    """

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--escenario", default="base", 
                        choices=["base", "optimista", "pesimista", "todos"])
    parser.add_argument("--data-dir", type=Path, default="data")
    parser.add_argument("--output-dir", type=Path, default="outputs")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    
    if args.escenario == "todos":
        kpis_all = {}
        for esc in ["base", "optimista", "pesimista"]:
            kpis_all[esc] = main(esc, args.data_dir, args.output_dir)
        # generar comparativa final
    else:
        main(args.escenario, args.data_dir, args.output_dir)
```

## Logging

- Cada fase logea su inicio, su fin, y un resumen numérico (ej. "Fase 7 — CAPEX total calculado: 587 M€").
- En modo `--verbose`, logea estadísticas detalladas de cada DataFrame producido.
- Usar timestamps en el formato del log para poder medir tiempos de cada fase.
- Si una fase falla, logear el traceback completo y abortar — no seguir con datos parciales.

## Tiempo objetivo

La pipeline completa para un escenario debe ejecutarse en **menos de 30 segundos** en una máquina razonable. Si pasa de un minuto, hay que profilar y optimizar (probablemente el cuello de botella es el cumulative traffic en grafos grandes — usar NumPy en vez de bucles Python).

## Reproducibilidad

- Cada ejecución guarda en `outputs/escenario_<nombre>/run_metadata.json`:
    - Timestamp de la ejecución
    - Hash git del código (si está bajo git)
    - Hash MD5 de los datos de entrada
    - Versión de las dependencias clave
    - El escenario completo de `decisiones.yaml`
- Esto permite trazabilidad: si dos meses después el profesor pregunta "¿de dónde sale este número?", se puede recuperar la ejecución exacta.

## Validación final

Tras un `python main.py --todos`, debe quedar una estructura como:

```
outputs/
├── escenario_base/
│   ├── img/
│   │   ├── topologia_anillos.png
│   │   ├── topologia_completa.png
│   │   ├── capex_por_año.png
│   │   ├── ingresos_vs_costes.png
│   │   └── ... 
│   ├── plan_despliegue.xlsx
│   ├── oferta_tecnica.pdf
│   ├── oferta_economica.pdf
│   ├── resumen_ejecutivo.pdf
│   └── run_metadata.json
├── escenario_optimista/  (igual estructura)
├── escenario_pesimista/  (igual estructura)
└── comparativa_3escenarios.pdf
```

## Cuando termines

- Ejecuta `python main.py --todos` y reporta tiempos por fase y por escenario.
- Verifica que los 3 escenarios producen outputs distintos pero coherentes (NPV pesimista < base < optimista, payback pesimista > base > optimista, etc.).
- Crea un test de integración mínimo en `tests/test_main.py` que ejecute `main(escenario='base')` con datos sintéticos y verifique que produce los archivos esperados.

## Listo para entregar

A partir de aquí, cada ronda de negociación con la administración o cada ajuste del profesor se traduce en:
1. Editar `decisiones.yaml`
2. Ejecutar `python main.py --todos`
3. Recoger los nuevos PDFs

Eso es lo que el profesor pidió cuando dijo *"todo esto ha de estar automatizado"*.

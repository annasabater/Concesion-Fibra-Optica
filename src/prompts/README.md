# Carpeta de prompts — Proyecto ABAST

Esta carpeta contiene los prompts numerados que se ejecutan en orden para generar el código del proyecto. Cada prompt produce un módulo en `src/` y, opcionalmente, sus tests en `tests/`.

## Cómo usarlos

1. Abre Claude Code en la raíz del proyecto. Leerá `CLAUDE.md` automáticamente y tendrá el contexto completo desde el primer mensaje.

2. Ejecuta los prompts en orden numérico. Para cada prompt:
   - Pega el contenido de `NN_xxx.md` en Claude Code (o usa `/include`)
   - Claude genera el código del módulo correspondiente
   - Revisa, ajusta si necesario, ejecuta los tests y commiteas

3. **No saltes prompts.** Los módulos posteriores asumen que los anteriores están terminados. Si algo no encaja, vuelve atrás.

## Mapa de prompts y a qué TAREA del profe corresponden

| Prompt | Módulo | Tarea profe | Fecha objetivo |
|--------|--------|-------------|----------------|
| `00_setup.md` | estructura inicial + deps | preparación | día 1 |
| `01_load.md` | `load.py` — carga Excel y YAML | TAREA 5 | 12/05 |
| `02_topology.md` | `topology.py` — grafo NetworkX | día 1+1 | mañana |
| `03_traffic.md` | `traffic.py` — tráfico ABAST + mayorista | TAREA 5 | 12/05 |
| `04_equipment.md` | `equipment.py` — selección equipos por nodo | TAREA 5 | 12/05 |
| `05_capex.md` | `capex.py` — inversiones por año y anillo | TAREA 6 | 19/05 |
| `06_opex.md` | `opex.py` — costes operativos plurianuales | TAREA 7 | 02/06 |
| `07_revenue.md` | `revenue.py` — ingresos plurianuales | TAREA 7 | 02/06 |
| `08_pnl.md` | `pnl.py` — cuenta de resultados + KPIs | TAREA 7 | 02/06 |
| `09_visualize.md` | `visualize.py` — diagramas topología | TAREA 6 (oferta técnica) | 26/05 |
| `10_report.md` | `report.py` — Excel salida + PDF | TAREA 6 + 7 | 26/05 + 09/06 |
| `11_main.md` | `main.py` — orquestador end-to-end | continuo | toda la vida |

## Orden recomendado por entrega

- **Para topología**: `00 → 01 → 02 → 09` (sólo la parte de visualización topológica de 09).
- **Para 12/05 (TAREA 5 — solución técnica)**: añadir `03 → 04`.
- **Para 26/05 (oferta técnica)**: añadir `05 → 09 (completo) → 10` (PDF de oferta técnica).
- **Para 09/06 (oferta económica)**: añadir `06 → 07 → 08 → 10` (PDF de oferta económica).
- **Para 30/06 (defensa final)**: iterar sobre todo, ajustar `decisiones.yaml`, regenerar.

## Anti-patrones a evitar

- **No metas decisiones de negocio en el código.** Todo lo que cambia entre escenarios va a `decisiones.yaml`.
- **No hardcodees rutas absolutas.** Usa `Path(__file__).parent / "data" / "..."`.
- **No mezcles cálculo y presentación.** Los módulos `*.py` calculan; `visualize.py` y `report.py` presentan.
- **No optimices prematuramente.** Primero que funcione end-to-end con los 3 escenarios. Después se optimiza si sobra tiempo.
- **No pierdas la trazabilidad.** Cualquier número en la oferta debe poder rastrearse a una línea del Excel y a un valor de `decisiones.yaml`.

## Si algo se atasca

- El profesor cambiará cosas durante el cuatrimestre (es seguro). Cada cambio se traduce en una línea de `CLAUDE.md` que actualizas + un parámetro de `decisiones.yaml`.
- Las negociaciones con la administración te obligarán a generar variantes en frío. Cada variante = un escenario nuevo en `decisiones.yaml`.
- Si el prompt de un módulo no produce código que funciona a la primera, no te lo tomes como fallo — es iterativo. Pega el error en Claude Code y deja que corrija.

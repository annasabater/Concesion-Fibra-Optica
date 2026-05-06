# Prompt 00 — Setup inicial del proyecto

> **Pega este prompt completo en Claude Code al iniciar la primera sesión.**

Lee primero `CLAUDE.md` para entender el contexto completo del proyecto (concurso público a 20 años, red de fibra para territorio ABAST, 4 grupos compitiendo, modelo de cálculo en 10 pasos).

## Tu tarea ahora

Crear la estructura inicial del proyecto: carpetas, archivos vacíos de cada módulo con su docstring, `requirements.txt`, `decisiones.yaml` con los 3 escenarios completos, `.gitignore`, y `README.md` orientado a humanos. **No implementes la lógica de los módulos todavía** — eso vendrá en los prompts 01–11.

## Pasos a ejecutar

1. **Crear la estructura de carpetas**:
   ```
   data/
   src/
   outputs/escenario_base/
   outputs/escenario_optimista/
   outputs/escenario_pesimista/
   tests/
   ```

2. **Crear stubs de los módulos** en `src/`. Cada archivo debe tener sólo:
   - Docstring de módulo describiendo qué hace
   - `from __future__ import annotations` y los imports estándar
   - Función principal vacía (raise NotImplementedError) con type hints y docstring estilo Google

   Módulos: `load.py`, `topology.py`, `traffic.py`, `equipment.py`, `capex.py`, `opex.py`, `revenue.py`, `pnl.py`, `visualize.py`, `report.py`. Crear también `src/__init__.py` y `tests/__init__.py` vacíos.

3. **Crear `main.py`** en la raíz con un esqueleto:
   - Argparse con `--escenario` (default `base`), `--data-dir`, `--output-dir`
   - Importa todos los módulos de `src/`
   - Función `main(escenario: str)` que llama secuencialmente a las 10 fases (todas vacías por ahora con `logging.info`)
   - `if __name__ == "__main__": main()`
   - Setup de logging básico

4. **Crear `requirements.txt`** con: `pandas`, `openpyxl`, `networkx`, `matplotlib`, `pyyaml`, `numpy`, `numpy-financial`, `reportlab`, `pytest`. Pinear versiones razonables.

5. **Crear `data/decisiones.yaml`** con los **3 escenarios** (base, optimista, pesimista) usando exactamente la estructura definida en `CLAUDE.md`. Comenta cada parámetro brevemente para que sea autoexplicativo.

6. **Crear `.gitignore`** que excluya `outputs/`, `__pycache__/`, `.venv/`, `*.pyc`, `.DS_Store`, `.idea/`, `.vscode/`, archivos temporales de Excel (`~$*.xlsx`).

7. **Crear `README.md`** humano (no confundir con el de `prompts/`) con:
   - Qué es el proyecto en una frase
   - Cómo instalar (`python -m venv .venv` + `pip install -r requirements.txt`)
   - Cómo ejecutar (`python main.py --escenario base`)
   - Estructura de carpetas
   - Enlace a `CLAUDE.md` para el contexto completo

## Validación

Al terminar:

- Ejecutar `python -c "import src.load, src.topology, src.traffic, src.equipment, src.capex, src.opex, src.revenue, src.pnl, src.visualize, src.report"` no debe dar errores.
- Ejecutar `python main.py --escenario base` debe correr sin errores (aunque no haga nada útil aún) y mostrar logs de cada fase con `INFO`.
- `pip install -r requirements.txt` debe funcionar limpiamente en un venv nuevo.

## Cuando termines

Confirma con un resumen de qué archivos has creado, total de líneas, y qué se puede ejecutar ya. No empieces el siguiente módulo — eso es el prompt 01.

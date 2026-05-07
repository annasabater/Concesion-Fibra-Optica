# Proyecto ABAST — Concesión de red de fibra óptica a 20 años

> Este documento es el contexto persistente del proyecto. Léelo siempre antes de empezar cualquier tarea.

## Contexto del proyecto

Proyecto académico de la asignatura **Projectes de Xarxes i Sistemes de Telecomunicació II** del Máster en Telecomunicaciones (MET) de **La Salle URL**. Simula un **concurso público bajo el procedimiento de diálogo competitivo de la LCSP** (Ley de Contratos del Sector Público española).

Cuatro grupos de estudiantes representan cuatro empresas privadas que compiten por adjudicarse una **concesión de 20 años** para construir y explotar una red de fibra óptica en un territorio público ficticio llamado **ABAST**. La administración (también llamada ABAST) es el ente público que adjudica la concesión.

### Procedimiento del concurso

1. **Primera entrega**: oferta técnica (26/05/2026) + oferta económica (09/06/2026)
2. **Ronda de negociación**: la administración llama a cada empresa por separado y pide modificaciones concretas
3. **Oferta final**: tras incorporar cambios, defensa el 30/06/2026
4. **Evaluación**: por **suma ponderada** (no media). La mejor propuesta saca 10 en cada criterio y el resto se escalan a la baja. Hay nota individual + grupal.

### Modelo de negocio

Concesión a 20 años con **dos fuentes de ingreso**:

- **ABAST (autoprestación)**: la administración paga 1.000 €/mes por cada sede pública conectada e iluminada. Alta gratis (0 €).
- **Mayorista**: la empresa puede vender capacidad a otros operadores ya presentes en cada municipio. Alta de 1.500 € + 700 €/mes por sede mayorista. **NO se puede vender a clientes finales residenciales** — sólo wholesale.

### Restricciones contractuales clave

- **Reequilibrio económico** (mecanismo LCSP): si la realidad se desvía del plan financiero, se activa rebalancing. Si va mejor → la administración reclama parte del extra (clawback). Si va peor → la empresa reclama compensación. Esto obliga a que las premisas de la oferta sean coherentes y compensadas.
- **Cobertura obligatoria**: la red debe llegar a TODOS los 900 municipios del territorio y conectar las 5.000 sedes públicas (escuelas, comisarías, centros de salud, ayuntamientos).
- **Tope presupuestario** implícito (a confirmar con el profesor).

## Topología de la red

Tres capas jerárquicas. Las dos superiores las da la administración ya construidas; la capa de acceso la construye la empresa.

### Capa troncal (1.000 km, 10 nodos, 3 anillos T1/T2/T3, ya construida)

Los 3 anillos convergen en el nodo **A900**, que NO es sólo un hub de red sino un **DATA CENTER**: el CPD del operador, donde está el NOC, los servidores, los sistemas de información, y donde se hace la salida a internet pública para los clientes mayoristas. A900 está físicamente sobre los 3 anillos troncales (T1+T2+T3) y los 2 primeros anillos de agregación (A1+A2), siendo el punto único de fallo más crítico.

Cada anillo troncal tiene 4 nodos:

- T1: A900, A891 (gateway A11), A892 (gateway A10), A899 (gateway A3)
- T2: A900, A893 (gateway A9), A894 (gateway A8), A898 (gateway A4)
- T3: A900, A895 (gateway A7), A896 (gateway A6), A897 (gateway A5)

### Capa de agregación (2.000 km, 91 nodos, 11 anillos A1–A11, ya construida)

Los 11 anillos cuelgan de los nodos gateway que están a la vez en un anillo troncal. Distribución de nodos por anillo:

- A1: 11 nodos (cuelga de A900)
- A2: 12 nodos (cuelga de A900)
- A3 a A10: 8 nodos cada uno
- A11: 4 nodos

Los nodos de agregación están en los códigos A800–A890 del Excel.

### Capa de acceso (4.825 km a construir, 799 municipios, árbol multi-hop)

Cada municipio de acceso (códigos A1–A799) cuelga de un nodo de agregación a través de una cadena multi-hop de concentradores. Por ejemplo: `A1 → A300 → A630 → A752 → A774 → A800` (que está en el anillo A2). Los enlaces típicos son de 5–10 km, con casos atípicos hasta 77 km.

## Datos de partida

### Archivo: `data/topologia_municipios.xlsx`

Hoja principal **"Municipios y topologia de red"** con las siguientes columnas:

| Columna | Descripción |
|---------|-------------|
| Código | Identificador secuencial 1–900 |
| Hab | Habitantes del municipio |
| Sedes ABAST | Número de sedes públicas a conectar |
| Num Operadores | Operadores de telecomunicaciones ya presentes (1–5) |
| Municipio-origen servicio | Código del municipio (ej. A1, A300, A900) |
| Municipio-destino Acceso | Padre en el árbol de acceso (NA para nodos agregación/troncal) |
| Km | Distancia al destino de acceso |
| Municipio-destino Agregación | Sólo para nodos en anillos de agregación |
| Municipio destino troncal | Sólo para nodos en anillos troncales |
| Anillo agregación | Anillo asignado (A1, A2, ..., A11), o NA |
| Anillo troncal | Anillo asignado (T1, T2, T3), o NA |

**⚠️ Gotcha importante**: las celdas de los nodos 800–900 tienen FÓRMULAS Excel (`=+F804` etc.). Hay que cargar el Excel con `data_only=True` en openpyxl, o bien ignorar esas celdas para los nodos de agregación/troncal porque su `destino_acceso` es ellos mismos (terminadores del árbol).

**⚠️ Gotcha distribucional**: del análisis de los datos, casi el 88% de los municipios de acceso (793 de 900) terminan resolviendo a través de la cadena de destino al anillo A2. Es decir, A2 es el "anillo espina dorsal" de la red — concentra la mayoría del tráfico de acceso. Esto es deliberado del profesor; no es un error.

### Archivo: `data/parametros_economicos.xlsx`

Hoja **"Parámetros"** con tarifas, CAPEX y OPEX unitarios:

**Ingresos**:

- Alta sede ABAST: 0 €
- Recurrente sede ABAST: 1.000 €/mes
- Alta sede mayorista: 1.500 €
- Recurrente sede mayorista: 700 €/mes

**OPEX**:

- Mantenimiento fibra: 250 €/km·año
- Mantenimiento equipos activos: 10% del CAPEX activo
- Mantenimiento sistemas información: 10% del CAPEX SI
- Derechos de paso e impuestos: 3% de ingresos
- Costes ventas mayorista: 10% sobre ingresos mayorista
- Gastos generales: 700.000 €/año

**CAPEX**:

- Inversión nueva sede ABAST: 20.000 €
- Inversión nueva sede mayorista: 20.000 €
- Obra civil + cable urbano: 100 €/m
- Obra civil + cable acceso: 100 €/m
- Nodo agregación/troncal (chasis sin equipos): 100.000 €
- Equipo cliente: 300 €
- Equipo agregación 10 puertos 10/100/1000: 1.500 €
- Equipo agregación 20 puertos 10/100/1000: 5.000 €
- Equipo agregación 40 puertos 10/100/1000: 12.000 €
- Equipo troncal MPLS: 50.000 €
- Equipo troncal óptico 40 lambdas: 60.000 €

### Archivo: `data/decisiones.yaml`

Único archivo editable que contiene las palancas de decisión del grupo. Cambiar valores aquí debe recalcular toda la pipeline. Estructura recomendada:

```yaml
escenarios:
  base:
    mayorista:
      cuota_mercado:
        tipo: rampa  # equilibrio | agresivo | rampa
        alpha_objetivo: 0.40
        años_rampa: 8
      bw_por_hogar_mbps: 100
      habitantes_por_hogar: 2.5
      overbooking: 20
    abast:
      bw_por_sede_mbps: 100
      overbooking: 1
    equipos:
      umbral_10p_a_20p: 8
      umbral_20p_a_40p: 16
      umbral_40p_a_mpls: 36
    despliegue:
      estrategia: progresivo  # uniforme | priorizado | progresivo
      prioridad: hab_descendente
      km_max_anuales: 500
      sedes_max_anuales: 400
    datacenter_a900:
      capex_extra: 5000000
      opex_extra_anual: 500000
    descuento:
      tasa: 0.06
      años: 20

  optimista:
    mayorista:
      cuota_mercado:
        tipo: rampa
        alpha_objetivo: 0.50
        años_rampa: 6
      overbooking: 25
    # resto hereda de base

  pesimista:
    mayorista:
      cuota_mercado:
        tipo: rampa
        alpha_objetivo: 0.30
        años_rampa: 10
      overbooking: 15
    # resto hereda de base
```

## Flujo de cálculo (11 pasos)

1. **Carga de datos** (`load.py`): leer Excel, validar, normalizar
2. **Topología** (`topology.py`): construir grafo NetworkX dirigido con A900 como root
3. **Tráfico ABAST** (`traffic.py`): por municipio = `sedes_abast × 100 Mbps`
4. **Tráfico mayorista** (`traffic.py`): por municipio = `(hab/hab_por_hogar) × cuota_operadores × penetracion_fibra × 100 Mbps / overbooking`
5. **Geomarketing y viabilidad** (`geomarketing.py`): análisis de viabilidad por municipio, orden de despliegue, estimación PYMEs, decisión armario/local
6. **Tráfico acumulado** (`equipment.py`): BFS desde las hojas hacia A900, sumando
7. **Selección de equipo** (`equipment.py`): según tráfico acumulado, elegir 10p / 20p / 40p / MPLS / óptico 40λ
8. **CAPEX** (`capex.py`): obra civil + altas + equipos, agregado por anillo y por año según plan
9. **OPEX** (`opex.py`): mantenimiento + impuestos + costes ventas + generales, escalando con red activa
10. **Ingresos** (`revenue.py`): ABAST + mayorista por año, según conexión gradual
11. **Cuenta de resultados** (`pnl.py`): EBITDA, resultado neto, KPIs (NPV, IRR, payback) a 20 años

## Decisiones del grupo (las palancas variables)

Estas son las palancas que cada grupo elige y defiende en la oferta. Todas viven en `decisiones.yaml`:

1. **α (cuota mayorista)**: equilibrio `1/(n+1)`, agresivo `1/n`, o rampa `α(t)` creciente. Recomendación: rampa, porque es la más realista (no se llega el año 1 con cuota plena).
2. **BW por hogar mayorista**: 100 Mbps / 1 Gbps / tier mixto.
3. **Overbooking**: 1:20 residencial, 1:5 empresa, 1:1 ABAST.
4. **Plan de despliegue temporal**: cuántos km y sedes por año.
5. **Umbrales de equipo**: cuándo pasar de 10p a 20p a 40p (afecta CAPEX).
6. **Redundancia adicional**: caminos físicos extra a municipios críticos.
7. **CAPEX A900**: inversión específica en datacenter.

## Entregables y calendario

| Fecha | Tarea |
|-------|-------|
| 12/05/2026 | TAREA 5: equipos + solución técnica |
| 19/05/2026 | TAREA 6: diseño solución técnica |
| **26/05/2026** | **ENTREGA OFERTA TÉCNICA** |
| 02/06/2026 | TAREA 7: diseño modelo económico |
| **09/06/2026** | **ENTREGA OFERTA ECONÓMICA** |
| 16/06/2026 | TAREA 8: revisión + preparación oferta final |
| **30/06/2026** | **ENTREGA OFERTA FINAL + DEFENSA** |

## Convenciones de código

- **Python 3.11+**
- Stack: `pandas`, `networkx`, `openpyxl`, `matplotlib`, `pyyaml`, `numpy`, `numpy-financial` (para IRR), `reportlab` (para PDF), `seaborn` (opcional)
- Estructura modular: cada módulo expone funciones puras donde sea posible
- **Type hints** en todas las funciones públicas
- **Docstrings** estilo Google
- Tests unitarios mínimos en `tests/` — happy path, no full TDD
- **Logging** con `logging` standard library (no `print` en producción)
- `decisiones.yaml` es la **única** fuente de configuración variable
- `parametros_economicos.xlsx` y `topologia_municipios.xlsx` son datos fijos
- Output en `outputs/escenario_<nombre>/` por escenario
- Idioma código: variables y funciones en inglés, comentarios y docstrings en español

## Estructura del proyecto

```
proyecto-abast/
├── data/
│   ├── topologia_municipios.xlsx
│   ├── parametros_economicos.xlsx
│   └── decisiones.yaml
├── src/
│   ├── __init__.py
│   ├── load.py
│   ├── topology.py
│   ├── traffic.py
│   ├── geomarketing.py
│   ├── equipment.py
│   ├── capex.py
│   ├── opex.py
│   ├── revenue.py
│   ├── pnl.py
│   ├── visualize.py
│   └── report.py
├── outputs/
│   ├── escenario_base/
│   ├── escenario_optimista/
│   └── escenario_pesimista/
├── tests/
├── prompts/                 # carpeta de los prompts paso a paso
├── main.py
├── requirements.txt
├── README.md
└── CLAUDE.md                # este archivo
```

## Filosofía de trabajo

- **Iteración corta**: producir el primer end-to-end mínimo viable lo antes posible y refinar.
- **Reequilibrio = 3 escenarios**: SIEMPRE generar pesimista + base + optimista. Eso da defensa robusta ante el reequilibrio económico.
- **Recalcular barato**: cualquier cambio en `decisiones.yaml` debe regenerar todos los outputs en < 30 segundos.
- **Trazabilidad**: cada output (Excel, PDF, gráfica) debe poder rastrearse hasta los inputs que lo generaron. Versionar `decisiones.yaml` con git.

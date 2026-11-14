# legacy/ — material exclusivo de la tesis (no mantenido)

Esta carpeta conserva, solo como referencia histórica, el material que pertenecía
al trabajo de tesis original (CIB46) y que **no forma parte** del foco de este
repositorio (la charla de KCD Porto sobre Zero Trust en un core 5G cloud native).

**No se mantiene, no se prueba en CI y puede contener rutas o supuestos obsoletos.**
Está deliberadamente **fuera del alcance de los linters** del pipeline.

## Qué hay aquí

| Ruta | Qué es |
|---|---|
| `data-processing/` | Scripts Python de consolidación y figuras del experimento de la tesis. |
| `analysis/` | Análisis estadístico (ómnibus Kruskal-Wallis, post-hoc de Dunn, tamaños de efecto). |
| `transitions/` | Scripts `transition-to-c0..c3.sh`: transición imperativa entre las condiciones C0–C3 de la tesis. En el repo activo la transición es declarativa con `make condition C=cN`. |
| `docs/protocolo-experimental.md` | Protocolo experimental (hipótesis, condiciones C0–C3, muestreo, análisis). |
| `REPRODUCIBILITY.md` | Guía de reproducibilidad del artefacto para *artifact evaluation* y defensa de la tesis. |
| `CITATION.cff` | Metadatos de cita del testbed como artefacto académico. |

## Por qué está separado

El repositorio activo se reorientó desde el objetivo de tesis (contrastar las
hipótesis bajo las condiciones C0–C3) hacia una demostración para la charla. El
código de despliegue, las políticas de red y los scripts de ataque siguen vivos en
la raíz; lo que era puramente instrumentación de medición y escritura académica se
archivó aquí.

> Las rutas internas de estos ficheros pueden apuntar a ubicaciones previas al
> movimiento. No se corrigieron porque este material queda congelado.

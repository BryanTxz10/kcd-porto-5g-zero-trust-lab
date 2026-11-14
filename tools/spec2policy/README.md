# spec2policy — spec-as-policy para la SBI del core 5G

Deriva `CiliumNetworkPolicy` L7 (método + path HTTP) a partir del **estándar 3GPP**
y las cruza con lo **observado** en Hubble para producir el *blast radius map*
(Markdown + CSV) de la Fase 5. No necesita clúster: todo corre en local y en CI.

```
OpenAPI 3GPP Rel-17 ──┐
(extractos fijados     │
 por commit)           ├─► filas (NF destino, origen esperado, método, path) ─► CNP por NF
tabla productor/       │                                   │
consumidor (TS 23.501) ┘                                   ▼
                                           flujos Hubble (-o jsonpb, L7 http) ─► blast radius map
```

## Uso rápido

```bash
# desde la raíz del repo (o: cd tools/spec2policy && python -m spec2policy ...)
make spec2policy        # genera examples/out/ con los flujos sintéticos de ejemplo
make spec2policy-test   # ruff + pytest
```

```bash
cd tools/spec2policy
pip install -r requirements.txt          # PyYAML, pytest, ruff (versiones fijadas)
python -m spec2policy generate \
  --flows fixtures/hubble/sbi-sin-tls.jsonl --out examples/out --clean
python -m spec2policy generate --mode observed --flows capturas/*.jsonl --out out/
python -m spec2policy visibility          # CNP que fuerza visibilidad L7 en 7777
python -m spec2policy inspect-flows capturas/*.jsonl
```

Salida de `generate`:

| Fichero | Contenido |
|---|---|
| `out/cnp/spec2policy-sbi-<nf>.yaml` | Una CNP de ingress por NF; una regla `http` por operación, agrupada por NF origen |
| `out/cnp/spec2policy-sbi-l7-visibility.yaml` | CNP que activa el proxy L7 en TCP 7777 (necesaria para capturar) |
| `out/blast-radius-map.md` | Informe: fuentes, captura, efecto del SCP, resumen, por NF, radio de impacto, hallazgos |
| `out/blast-radius-map.csv` | Una fila por (punto de entrada, método, path) con estado y orígenes observados |

Modos: `standard` (todo lo que el estándar permite, haya sido observado o no) y
`observed` (solo las operaciones vistas en los flujos; falla si no hay L7).

## Entradas

- `data/openapi/*.yaml`: **extractos mínimos** (paths + métodos + servers + operationId)
  de los OpenAPI de 3GPP Rel-17, generados con `scripts/make_extracts.py` desde el
  mirror [jdegre/5GC_APIs](https://github.com/jdegre/5GC_APIs) fijado al commit
  `06137ac51e2cc19a6d767bb63a27563d27841b3a`. No se vendoriza el repo entero.
- `data/services.yaml`: tabla a mano de qué NF **produce** y **consume** cada
  servicio (TS 23.501 §7.2 / TS 23.502 §5.2), modelo del **SCP** como
  intermediario (modelo D, TS 23.501 Anexo E) y callbacks (notificaciones).
- `fixtures/hubble/*.jsonl`: flujos `hubble observe -o jsonpb`. Los incluidos son
  **sintéticos** (`scripts/make_fixtures.py`), realistas pero no capturados en el
  clúster. Contienen anomalías deliberadas para que el informe tenga hallazgos.

## Decisiones de modelado

- **SCP (trampa)**: en Open5GS la comunicación es indirecta; el productor ve al SCP
  como origen. Por eso cada operación vía SCP se modela dos veces: en el ingress del
  productor (origen `scp`) y en el ingress del SCP (origen: consumidores reales). La
  autorización *por consumidor* solo es posible en la segunda. Excepción: `nnrf-nfm`
  (registro/heartbeat), que las NF hacen directamente contra el NRF.
- **Paths con parámetros** → regex: `{param}` se traduce a `[^/?]+` y se añade
  `(\?.*)?` para la query string (desactivable con `--no-query-suffix`). Se asume
  coincidencia completa del path, como hace Envoy en Cilium.
- **Sin L7 no hay política L7**: si los flujos tienen tráfico a 7777 pero ninguna
  petición HTTP visible (mTLS activo, TS 33.501 §13.1), el informe lo avisa y
  `--mode observed` aborta.
- **Versiones de API**: se usan las de los OpenAPI Rel-17 (`nudr-dr` v2, `nudm-sdm` v2,
  `nnssf-nsselection` v2, resto v1). Si Open5GS 2.7.5 usa otra (p. ej. `/nudr-dr/v1`),
  el informe lo mostrará como `FUERA_DEL_ESTANDAR`; no está verificado.

## Estados del informe

| Estado | Significado |
|---|---|
| `OBSERVADO_CONFORME` | La operación se vio, desde un origen que el estándar permite |
| `OBSERVADO_ORIGEN_INESPERADO` | La operación se vio desde una NF que **no** es consumidora del servicio |
| `NO_OBSERVADO` | El estándar la permite pero nunca se vio (candidata a recortar) |
| `FUERA_DEL_ESTANDAR` | Petición que no casa con ninguna operación del OpenAPI del destino |
| `DESTINO_DESCONOCIDO` | El destino no es una NF modelada |

## Estructura

```
spec2policy/
  openapi.py   carga de extractos, template → regex
  topology.py  services.yaml → productores/consumidores/SCP/callbacks
  hubble.py    parser jsonpb (L7 http: method, url, pods y labels)
  analysis.py  cruce estándar × observado
  policy.py    generación de CNP
  report.py    Markdown + CSV
  cli.py       subcomandos generate / visibility / inspect-flows
tests/         pytest (56 tests, incl. determinismo de examples/out)
```

Estado: **NO verificado en clúster**. Ver `docs/pruebas-fase5.md`.

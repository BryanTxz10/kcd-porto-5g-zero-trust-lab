# Blast radius map — SBI del core 5G (plantilla)

> Plantilla **vacía** para la versión capturada en el clúster. Rellénala con la salida de
> `python -m spec2policy generate --flows <capturas reales> --out results/fase5`
> (ver `docs/pruebas-fase5.md`). El ejemplo con flujos **sintéticos** está en
> `tools/spec2policy/examples/out/blast-radius-map.md`.

## Contexto de la captura

| Campo | Valor |
|---|---|
| Fecha (UTC) | |
| Commit del repo | |
| Open5GS / chart | 2.7.5 / Gradiant 2.3.4 |
| Cilium | 1.15.4 |
| Modo SBI | sin TLS (con mTLS no hay visibilidad L7) |
| Cómo se obtuvo la visibilidad L7 | CNP `spec2policy-sbi-l7-visibility` / anotación |
| Escenario ejecutado | (registro UE, sesión PDU, vector de ataque…) |
| Fichero(s) de flujos | |

## Resumen

| Indicador | Valor |
|---|---|
| Servicios del estándar modelados | |
| Operaciones (método+path) permitidas por el estándar | |
| Filas de política (productor + SCP) | |
| OBSERVADO_CONFORME | |
| OBSERVADO_ORIGEN_INESPERADO | |
| NO_OBSERVADO | |
| FUERA_DEL_ESTANDAR | |

## Por punto de entrada (ingress de cada NF)

| NF | Op. permitidas | Orígenes según estándar | Orígenes observados | Conformes | Origen inesperado | No observadas |
|---|---|---|---|---|---|---|
| `amf` | | | | | | |
| `ausf` | | | | | | |
| `bsf` | | | | | | |
| `nrf` | | | | | | |
| `nssf` | | | | | | |
| `pcf` | | | | | | |
| `scp` | | | | | | |
| `smf` | | | | | | |
| `udm` | | | | | | |
| `udr` | | | | | | |

## Radio de impacto por consumidor comprometido

| Consumidor | Productores (estándar) | Op. estándar | Op. observadas | Productores observados | Op. alcanzables tras colapso SCP |
|---|---|---|---|---|---|
| `amf` | | | | | |
| `ausf` | | | | | |
| `bsf` | | | | | |
| `nssf` | | | | | |
| `pcf` | | | | | |
| `scp` | | | | | |
| `smf` | | | | | |
| `udm` | | | | | |
| `udr` | | | | | |

## Hallazgos (diferencia)

### Observado desde un origen inesperado

| Entrada | Método | Path | Origen esperado | Visto desde | Motivo |
|---|---|---|---|---|---|
| | | | | | |

### Peticiones fuera del estándar o a destino desconocido

| Destino | Método | Path | Origen | Tipo | Detalle |
|---|---|---|---|---|---|
| | | | | | |

## Efecto del SCP

(Qué porcentaje del ingress de los productores llega con origen `scp`; qué se pudo
autorizar solo en el ingress del SCP.)

## Limitaciones de esta captura

- Modo sin TLS: con mTLS activo (TS 33.501 §13.1) no se habría visto nada de esto.
- Cobertura del escenario: lo `NO_OBSERVADO` puede ser legítimo pero no ejercitado.
-

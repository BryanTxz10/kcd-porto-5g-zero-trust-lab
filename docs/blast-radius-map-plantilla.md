# Blast radius map — SBI del core 5G (captura real)

> Rellenada con la salida de
> `python -m spec2policy generate --flows <capturas reales> --out results/fase5`
> (ver `docs/pruebas-fase5.md`) sobre una captura del lab. El informe completo, con el
> detalle fila a fila, está en `results/fase5/blast-radius-map.md` y su `.csv`. El ejemplo
> con flujos **sintéticos** está en `tools/spec2policy/examples/out/blast-radius-map.md`.

## Contexto de la captura

| Campo | Valor |
|---|---|
| Fecha (UTC) | 2026-11-15, desde 14:35:39 (unos 3 min) |
| Commit del repo | `ab53db3` |
| Open5GS / chart | 2.7.5 / Gradiant 2.3.4 |
| Cilium | 1.15.4 |
| Modo SBI | sin TLS (con mTLS no hay visibilidad L7). `deploy_multus: true` |
| Cómo se obtuvo la visibilidad L7 | CNP `spec2policy-sbi-l7-visibility` (retirada al terminar) |
| Escenario ejecutado | `make cold-start` (recrea AMF, UPF, SMF, gNB y UE: registro de AMF y SMF en el NRF, registro del UE, sesión PDU, ping a 8.8.8.8), `make smoke` (re-registro del UE y discovery desde `sbi-probe`) y 60 s de heartbeats. Un solo UE, unos 3 min |
| Fichero(s) de flujos | `capturas/sbi_20261115T143539Z.jsonl` (7353 flujos, 12 MB, fuera del repo). Capturado con `hubble observe --namespace 5g-cp -f -o jsonpb` desde el agente de Cilium de node-worker1, donde corren todas las NF del plano de control |

## Resumen

| Indicador | Valor |
|---|---|
| Servicios del estándar modelados | 13 |
| Operaciones (método+path) permitidas por el estándar | 326 |
| Filas de política (productor + SCP) | 655 |
| OBSERVADO_CONFORME | 50 |
| OBSERVADO_ORIGEN_INESPERADO | 3 |
| NO_OBSERVADO | 602 |
| FUERA_DEL_ESTANDAR | 237 (199 `nnrf-nfm`, 38 `nudr-dr/v1`) |
| Flujos L7 (petición / respuesta) | 549 / 549 |
| Flujos SBI solo L3/L4 | 3341 |
| Flujos DROPPED | 20 |

## Por punto de entrada (ingress de cada NF)

| NF | Op. permitidas | Orígenes según estándar | Orígenes observados | Conformes | Origen inesperado | No observadas |
|---|---|---|---|---|---|---|
| `amf` | 19 | `nrf`, `pcf`, `scp`, `udm` | `scp` | 1 | 1 | 17 |
| `ausf` | 11 | `nrf`, `scp` | `scp` | 2 | 0 | 9 |
| `bsf` | 16 | `nrf`, `scp` | `scp` | 2 | 0 | 14 |
| `nrf` | 15 | `amf`, `ausf`, `bsf`, `nssf`, `pcf`, `scp`, `smf`, `udm`, `udr` | `sbi-probe`, `scp` | 5 | 1 | 9 |
| `nssf` | 2 | `nrf`, `scp` | — | 0 | 0 | 2 |
| `pcf` | 9 | `nrf`, `scp` | `scp` | 3 | 0 | 6 |
| `scp` | 318 | `amf`, `ausf`, `bsf`, `nrf`, `nssf`, `pcf`, `scp`, `smf`, `udm`, `udr` | `amf`, `ausf`, `nrf`, `pcf`, `smf` | 23 | 0 | 295 |
| `smf` | 12 | `nrf`, `pcf`, `scp` | `scp` | 3 | 1 | 8 |
| `udm` | 74 | `nrf`, `scp` | `scp` | 11 | 0 | 63 |
| `udr` | 179 | `nrf`, `scp` | — | 0 | 0 | 179 |

## Radio de impacto por consumidor comprometido

| Consumidor | Productores (estándar) | Op. estándar | Op. observadas | Productores observados | Op. alcanzables tras colapso SCP |
|---|---|---|---|---|---|
| `amf` | `ausf`, `nrf`, `nssf`, `pcf`, `smf`, `udm` | 106 | 11 | `ausf`, `pcf`, `smf`, `udm` | 317 |
| `ausf` | `nrf`, `udm` | 22 | 2 | `udm` | 317 |
| `bsf` | `nrf` | 15 | 0 | — | 317 |
| `nssf` | `nrf` | 15 | 0 | — | 317 |
| `pcf` | `amf`, `bsf`, `nrf`, `udr` | 224 | 2 | `bsf` | 317 |
| `scp` | `nrf` | 15 | 5 | `nrf` | 317 |
| `smf` | `amf`, `nrf`, `pcf`, `udm` | 101 | 8 | `amf`, `pcf`, `udm` | 317 |
| `udm` | `amf`, `nrf`, `udr` | 209 | 0 | — | 317 |
| `udr` | `nrf` | 15 | 0 | — | 317 |

## Hallazgos (diferencia)

### Observado desde un origen inesperado

| Entrada | Método | Path | Origen esperado | Visto desde | Motivo |
|---|---|---|---|---|---|
| `amf` | POST | `/nnrf-nfm/v1/nf-status-notify` | `nrf` | `scp`×2 | Open5GS entrega el callback del NRF a través del SCP |
| `smf` | POST | `/nnrf-nfm/v1/nf-status-notify` | `nrf` | `scp`×2 | ídem |
| `nrf` | GET | `/nnrf-disc/v1/nf-instances` | `scp` | `sbi-probe`×1 | esperado: el discovery del smoke sale de `sbi-probe`, que no está en la tabla de NF |

### Peticiones fuera del estándar o a destino desconocido

Resumen agrupado (IMSI e IDs de instancia normalizados). El detalle completo está en
`results/fase5/blast-radius-map.md`.

| Destino | Método | Path | Origen | Tipo | Detalle |
|---|---|---|---|---|---|
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/{nfInstanceId}` | las 8 NF salvo NRF y SCP | destino inesperado | heartbeats al NRF enviados vía SCP (unos 20 por NF en 3 min) |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances[/{nfInstanceId}]` | `amf`, `smf` | destino inesperado | lectura de perfiles de NF vía SCP |
| `scp` | POST | `/nnrf-nfm/v1/subscriptions` | `amf`, `smf` | destino inesperado | suscripciones al NRF vía SCP |
| `scp`, `udr` | GET, PUT, DELETE | `/nudr-dr/v1/...` | `udm`, `pcf`, `scp` | fuera del estándar | Open5GS 2.7.5 usa `nudr-dr/v1`; la tabla modela `v2` (Rel-17). Por eso el UDR sale con 0 conformes |

En total, 199 peticiones `nnrf-nfm` y 38 `nudr-dr/v1`. Las `nnrf-nfm` no están fuera
del estándar en sí: `spec2policy` modela `nnrf-nfm` como directo al NRF (la excepción
habitual del modelo D de TS 23.501 Anexo E), y Open5GS lo manda por el SCP.

## Efecto del SCP

Todo lo observado en la entrada de los productores llega con origen `scp`. La única
excepción es la petición de discovery de `sbi-probe` al NRF, que va directa. En Open5GS
2.7.5 pasan por el SCP también el registro y los heartbeats al NRF (`nnrf-nfm`) y los
callbacks `nf-status-notify`.

Consecuencias:

- La entrada de cada productor solo puede decir «del SCP, estas operaciones». La
  autorización por consumidor solo se puede hacer en la entrada del SCP, que concentra
  318 de las operaciones permitidas.
- Si el SCP reenvía sin autorización propia, cualquier NF comprometida alcanza **317
  operaciones**, también una NF que en la captura no pidió nada (BSF, NSSF, UDR) o una
  que solo hizo 11 (AMF, con 106 permitidas por el estándar).
- Lo observado es una fracción pequeña de lo permitido (AMF 11 de 106, PCF 2 de 224,
  SMF 8 de 101). Es una cota baja: la captura cubre un solo UE durante unos 3 min.

## Limitaciones de esta captura

- Modo sin TLS: con mTLS activo (TS 33.501 §13.1) no se habría visto nada de esto.
- Cobertura del escenario: lo `NO_OBSERVADO` puede ser legítimo pero no ejercitado. Un
  solo UE, unos 3 min. Sin handover, SMS, desregistro explícito ni varios slices.
- Los 237 `FUERA_DEL_ESTANDAR` son diferencias de modelo (`nnrf-nfm` vía SCP,
  `nudr-dr/v1`), no tráfico anómalo.
- 20 flujos DROPPED, ninguno de la SBI legítima. 16 son PFCP (8805) del SMF a la IP del
  UPF anterior, recreado por `make cold-start`. 4 son del SMF al SCP hacia un puerto
  efímero, probablemente respuestas de conexiones abiertas antes de aplicar la CNP de
  visibilidad (sin demostrar).
- La CNP de visibilidad es aditiva y abre todo 5g-cp al 7777 mientras está aplicada:
  durante la captura `sbi-probe` podía listar perfiles del NRF. Se retiró al terminar y
  `make demo-l7-ciega` volvió a dar 403.

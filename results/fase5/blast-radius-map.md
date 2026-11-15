# Blast radius map — SBI del core 5G (spec-as-policy)

Cruce entre lo que el estándar 3GPP permite en la SBI (OpenAPI Rel-17 + tabla productor/consumidor de TS 23.501 §7.2), lo observado con Hubble (L7) y la diferencia. Generado por `tools/spec2policy`; no editar a mano.

## Fuentes

- Tabla productor/consumidor: `data/services.yaml`
- OpenAPI 3GPP (extractos, mirror fijado por commit):
  - `namf-comm` Namf_Communication 1.2.4 — `jdegre/5GC_APIs@06137ac51e2c:TS29518_Namf_Communication.yaml` (16 op.)
  - `nausf-auth` AUSF API 1.2.3 — `jdegre/5GC_APIs@06137ac51e2c:TS29509_Nausf_UEAuthentication.yaml` (10 op.)
  - `nbsf-management` Nbsf_Management 1.3.1 — `jdegre/5GC_APIs@06137ac51e2c:TS29521_Nbsf_Management.yaml` (15 op.)
  - `nnrf-disc` NRF NFDiscovery Service 1.2.7 — `jdegre/5GC_APIs@06137ac51e2c:TS29510_Nnrf_NFDiscovery.yaml` (6 op.)
  - `nnrf-nfm` NRF NFManagement Service 1.2.7 — `jdegre/5GC_APIs@06137ac51e2c:TS29510_Nnrf_NFManagement.yaml` (9 op.)
  - `nnssf-nsselection` NSSF NS Selection 2.2.1 — `jdegre/5GC_APIs@06137ac51e2c:TS29531_Nnssf_NSSelection.yaml` (1 op.)
  - `npcf-am-policy-control` Npcf_AMPolicyControl 1.2.1 — `jdegre/5GC_APIs@06137ac51e2c:TS29507_Npcf_AMPolicyControl.yaml` (4 op.)
  - `npcf-smpolicycontrol` Npcf_SMPolicyControl API 1.2.4 — `jdegre/5GC_APIs@06137ac51e2c:TS29512_Npcf_SMPolicyControl.yaml` (4 op.)
  - `nsmf-pdusession` Nsmf_PDUSession 1.2.6 — `jdegre/5GC_APIs@06137ac51e2c:TS29502_Nsmf_PDUSession.yaml` (10 op.)
  - `nudm-sdm` Nudm_SDM 2.2.5 — `jdegre/5GC_APIs@06137ac51e2c:TS29503_Nudm_SDM.yaml` (35 op.)
  - `nudm-ueau` Nudm_UEAU 1.2.2 — `jdegre/5GC_APIs@06137ac51e2c:TS29503_Nudm_UEAU.yaml` (7 op.)
  - `nudm-uecm` Nudm_UECM 1.2.6 — `jdegre/5GC_APIs@06137ac51e2c:TS29503_Nudm_UECM.yaml` (31 op.)
  - `nudr-dr` Nudr_DataRepository API OpenAPI file 2.2.5 — `jdegre/5GC_APIs@06137ac51e2c:TS29504_Nudr_DR.yaml` (178 op.)
- Flujos Hubble (`hubble observe -o jsonpb`):
  - `../../capturas/sbi_20261115T143539Z.jsonl`

## Captura

| Métrica | Valor |
|---|---|
| Líneas leídas | 7353 |
| JSON inválido | 0 |
| Flujos | 7353 |
| Peticiones HTTP (L7 REQUEST) | 549 |
| Respuestas HTTP (L7 RESPONSE) | 549 |
| Flujos L3/L4 hacia TCP 7777 sin L7 | 3341 |
| Flujos L3/L4 a otros puertos | 2914 |
| DROPPED | 20 |
| Peticiones L7 a otros puertos (ignoradas) | 0 |

> ℹ️ Muchos más flujos L3/L4 al puerto SBI que peticiones HTTP: parte del tráfico no pasa por el proxy L7 (NF sin regla http o conexiones cifradas).

## Efecto del SCP (comunicación indirecta)

Con SCP (modelo D), el productor ve como origen al SCP para todos los servicios salvo: nnrf-nfm. La autorización por consumidor solo es posible en la entrada del SCP.

Por eso cada operación aparece dos veces en el detalle cuando va vía SCP: en la entrada del **productor** (origen esperado: `scp`) y en la entrada del **SCP** (origen esperado: los consumidores reales). La política por consumidor se decide en la segunda.

## Resumen

| Indicador | Valor |
|---|---|
| Servicios del estándar modelados | 13 |
| Operaciones (método+path) permitidas por el estándar | 326 |
| Callbacks modelados | 12 |
| Filas de política (productor + SCP) | 655 |
| OBSERVADO_CONFORME | 50 |
| OBSERVADO_ORIGEN_INESPERADO | 3 |
| NO_OBSERVADO | 602 |
| FUERA_DEL_ESTANDAR (peticiones sin operación en la API) | 237 |

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

Si un atacante toma el pod de la NF *consumidor*, ¿a cuántas operaciones de qué productores le da acceso la política? «Estándar» = política derivada del OpenAPI aplicada en la entrada del SCP. «Observado» = lo que realmente se vio hacer a esa NF. «Colapso SCP» = lo que el productor permite desde `scp`, es decir, lo que ese atacante alcanza si el SCP reenvía sin autorización propia (todo lo que el SCP puede pedir a cualquier productor).

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
| `amf` | POST | `/nnrf-nfm/v1/nf-status-notify` | `nrf` | `scp`×2 | no es consumidor de este servicio según el estándar |
| `nrf` | GET | `/nnrf-disc/v1/nf-instances` | `scp` | `sbi-probe`×1 | NF desconocida para la tabla |
| `smf` | POST | `/nnrf-nfm/v1/nf-status-notify` | `nrf` | `scp`×2 | no es consumidor de este servicio según el estándar |

### Peticiones fuera del estándar o a destino desconocido

| Destino | Método | Path | Origen | Tipo | Detalle |
|---|---|---|---|---|---|
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/d65fd080-e0fe-41f1-b896-ebb3443d9a0c` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/d65fd080-e0fe-41f1-b896-ebb3443d9a0c no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/d65fd080-e0fe-41f1-b896-ebb3443d9a0c` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/d65fd080-e0fe-41f1-b896-ebb3443d9a0c no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/d65fd080-e0fe-41f1-b896-ebb3443d9a0c` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/d65fd080-e0fe-41f1-b896-ebb3443d9a0c no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/d65fd080-e0fe-41f1-b896-ebb3443d9a0c` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/d65fd080-e0fe-41f1-b896-ebb3443d9a0c no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PUT | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | PUT /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | POST | `/nnrf-nfm/v1/subscriptions` | `amf` | FUERA_DEL_ESTANDAR | POST /nnrf-nfm/v1/subscriptions no está en la API de scp |
| `scp` | POST | `/nnrf-nfm/v1/subscriptions` | `amf` | FUERA_DEL_ESTANDAR | POST /nnrf-nfm/v1/subscriptions no está en la API de scp |
| `scp` | POST | `/nnrf-nfm/v1/subscriptions` | `amf` | FUERA_DEL_ESTANDAR | POST /nnrf-nfm/v1/subscriptions no está en la API de scp |
| `scp` | POST | `/nnrf-nfm/v1/subscriptions` | `amf` | FUERA_DEL_ESTANDAR | POST /nnrf-nfm/v1/subscriptions no está en la API de scp |
| `scp` | POST | `/nnrf-nfm/v1/subscriptions` | `amf` | FUERA_DEL_ESTANDAR | POST /nnrf-nfm/v1/subscriptions no está en la API de scp |
| `scp` | POST | `/nnrf-nfm/v1/subscriptions` | `amf` | FUERA_DEL_ESTANDAR | POST /nnrf-nfm/v1/subscriptions no está en la API de scp |
| `scp` | POST | `/nnrf-nfm/v1/subscriptions` | `amf` | FUERA_DEL_ESTANDAR | POST /nnrf-nfm/v1/subscriptions no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances` | `amf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/bbd800ac-e0fe-41f1-9688-9540dc79a86e` | `amf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/bbd800ac-e0fe-41f1-9688-9540dc79a86e no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `amf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `amf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `amf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `amf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `amf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `amf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/bbaecd36-e0fe-41f1-ad28-2f8c36056e0a` | `amf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/bbaecd36-e0fe-41f1-ad28-2f8c36056e0a no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/d65fd080-e0fe-41f1-b896-ebb3443d9a0c` | `amf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/d65fd080-e0fe-41f1-b896-ebb3443d9a0c no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72` | `amf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72 no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PUT | `/nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0` | `smf` | FUERA_DEL_ESTANDAR | PUT /nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0 no está en la API de scp |
| `scp` | POST | `/nnrf-nfm/v1/subscriptions` | `smf` | FUERA_DEL_ESTANDAR | POST /nnrf-nfm/v1/subscriptions no está en la API de scp |
| `scp` | POST | `/nnrf-nfm/v1/subscriptions` | `smf` | FUERA_DEL_ESTANDAR | POST /nnrf-nfm/v1/subscriptions no está en la API de scp |
| `scp` | POST | `/nnrf-nfm/v1/subscriptions` | `smf` | FUERA_DEL_ESTANDAR | POST /nnrf-nfm/v1/subscriptions no está en la API de scp |
| `scp` | POST | `/nnrf-nfm/v1/subscriptions` | `smf` | FUERA_DEL_ESTANDAR | POST /nnrf-nfm/v1/subscriptions no está en la API de scp |
| `scp` | POST | `/nnrf-nfm/v1/subscriptions` | `smf` | FUERA_DEL_ESTANDAR | POST /nnrf-nfm/v1/subscriptions no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances` | `smf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/bbd800ac-e0fe-41f1-9688-9540dc79a86e` | `smf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/bbd800ac-e0fe-41f1-9688-9540dc79a86e no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `smf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `smf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `smf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `smf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `smf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `smf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/bbaecd36-e0fe-41f1-ad28-2f8c36056e0a` | `smf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/bbaecd36-e0fe-41f1-ad28-2f8c36056e0a no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72` | `smf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72 no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `smf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | GET | `/nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0` | `smf` | FUERA_DEL_ESTANDAR | GET /nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ee53ade2-e0fe-41f1-80e7-0f685d9f2b72 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | GET | `/nudr-dr/v1/subscription-data/imsi-999700000000001/authentication-data/authentication-subscription` | `udm` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/subscription-data/imsi-999700000000001/authentication-data/authentication-subscription no está en la API de scp |
| `udr` | GET | `/nudr-dr/v1/subscription-data/imsi-999700000000001/authentication-data/authentication-subscription` | `scp` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/subscription-data/imsi-999700000000001/authentication-data/authentication-subscription no está en la API de udr |
| `scp` | PUT | `/nudr-dr/v1/subscription-data/imsi-999700000000001/authentication-data/authentication-status` | `udm` | FUERA_DEL_ESTANDAR | PUT /nudr-dr/v1/subscription-data/imsi-999700000000001/authentication-data/authentication-status no está en la API de scp |
| `udr` | PUT | `/nudr-dr/v1/subscription-data/imsi-999700000000001/authentication-data/authentication-status` | `scp` | FUERA_DEL_ESTANDAR | PUT /nudr-dr/v1/subscription-data/imsi-999700000000001/authentication-data/authentication-status no está en la API de udr |
| `scp` | PUT | `/nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/amf-3gpp-access` | `udm` | FUERA_DEL_ESTANDAR | PUT /nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/amf-3gpp-access no está en la API de scp |
| `udr` | PUT | `/nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/amf-3gpp-access` | `scp` | FUERA_DEL_ESTANDAR | PUT /nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/amf-3gpp-access no está en la API de udr |
| `scp` | GET | `/nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/am-data` | `udm` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/am-data no está en la API de scp |
| `udr` | GET | `/nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/am-data` | `scp` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/am-data no está en la API de udr |
| `scp` | GET | `/nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/smf-selection-subscription-data` | `udm` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/smf-selection-subscription-data no está en la API de scp |
| `udr` | GET | `/nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/smf-selection-subscription-data` | `scp` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/smf-selection-subscription-data no está en la API de udr |
| `scp` | GET | `/nudr-dr/v1/policy-data/ues/imsi-999700000000001/am-data` | `pcf` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/policy-data/ues/imsi-999700000000001/am-data no está en la API de scp |
| `udr` | GET | `/nudr-dr/v1/policy-data/ues/imsi-999700000000001/am-data` | `scp` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/policy-data/ues/imsi-999700000000001/am-data no está en la API de udr |
| `scp` | GET | `/nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/sm-data` | `udm` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/sm-data no está en la API de scp |
| `udr` | GET | `/nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/sm-data` | `scp` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/sm-data no está en la API de udr |
| `scp` | GET | `/nudr-dr/v1/policy-data/ues/imsi-999700000000001/sm-data` | `pcf` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/policy-data/ues/imsi-999700000000001/sm-data no está en la API de scp |
| `udr` | GET | `/nudr-dr/v1/policy-data/ues/imsi-999700000000001/sm-data` | `scp` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/policy-data/ues/imsi-999700000000001/sm-data no está en la API de udr |
| `scp` | PUT | `/nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/smf-registrations/1` | `udm` | FUERA_DEL_ESTANDAR | PUT /nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/smf-registrations/1 no está en la API de scp |
| `udr` | PUT | `/nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/smf-registrations/1` | `scp` | FUERA_DEL_ESTANDAR | PUT /nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/smf-registrations/1 no está en la API de udr |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | DELETE | `/nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/smf-registrations/1` | `udm` | FUERA_DEL_ESTANDAR | DELETE /nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/smf-registrations/1 no está en la API de scp |
| `udr` | DELETE | `/nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/smf-registrations/1` | `scp` | FUERA_DEL_ESTANDAR | DELETE /nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/smf-registrations/1 no está en la API de udr |
| `scp` | GET | `/nudr-dr/v1/subscription-data/imsi-999700000000001/authentication-data/authentication-subscription` | `udm` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/subscription-data/imsi-999700000000001/authentication-data/authentication-subscription no está en la API de scp |
| `udr` | GET | `/nudr-dr/v1/subscription-data/imsi-999700000000001/authentication-data/authentication-subscription` | `scp` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/subscription-data/imsi-999700000000001/authentication-data/authentication-subscription no está en la API de udr |
| `scp` | PUT | `/nudr-dr/v1/subscription-data/imsi-999700000000001/authentication-data/authentication-status` | `udm` | FUERA_DEL_ESTANDAR | PUT /nudr-dr/v1/subscription-data/imsi-999700000000001/authentication-data/authentication-status no está en la API de scp |
| `udr` | PUT | `/nudr-dr/v1/subscription-data/imsi-999700000000001/authentication-data/authentication-status` | `scp` | FUERA_DEL_ESTANDAR | PUT /nudr-dr/v1/subscription-data/imsi-999700000000001/authentication-data/authentication-status no está en la API de udr |
| `scp` | PUT | `/nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/amf-3gpp-access` | `udm` | FUERA_DEL_ESTANDAR | PUT /nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/amf-3gpp-access no está en la API de scp |
| `udr` | PUT | `/nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/amf-3gpp-access` | `scp` | FUERA_DEL_ESTANDAR | PUT /nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/amf-3gpp-access no está en la API de udr |
| `scp` | GET | `/nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/am-data` | `udm` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/am-data no está en la API de scp |
| `udr` | GET | `/nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/am-data` | `scp` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/am-data no está en la API de udr |
| `scp` | GET | `/nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/smf-selection-subscription-data` | `udm` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/smf-selection-subscription-data no está en la API de scp |
| `udr` | GET | `/nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/smf-selection-subscription-data` | `scp` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/smf-selection-subscription-data no está en la API de udr |
| `scp` | GET | `/nudr-dr/v1/policy-data/ues/imsi-999700000000001/am-data` | `pcf` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/policy-data/ues/imsi-999700000000001/am-data no está en la API de scp |
| `udr` | GET | `/nudr-dr/v1/policy-data/ues/imsi-999700000000001/am-data` | `scp` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/policy-data/ues/imsi-999700000000001/am-data no está en la API de udr |
| `scp` | GET | `/nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/sm-data` | `udm` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/sm-data no está en la API de scp |
| `udr` | GET | `/nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/sm-data` | `scp` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/subscription-data/imsi-999700000000001/99970/provisioned-data/sm-data no está en la API de udr |
| `scp` | GET | `/nudr-dr/v1/policy-data/ues/imsi-999700000000001/sm-data` | `pcf` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/policy-data/ues/imsi-999700000000001/sm-data no está en la API de scp |
| `udr` | GET | `/nudr-dr/v1/policy-data/ues/imsi-999700000000001/sm-data` | `scp` | FUERA_DEL_ESTANDAR | GET /nudr-dr/v1/policy-data/ues/imsi-999700000000001/sm-data no está en la API de udr |
| `scp` | PUT | `/nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/smf-registrations/1` | `udm` | FUERA_DEL_ESTANDAR | PUT /nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/smf-registrations/1 no está en la API de scp |
| `udr` | PUT | `/nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/smf-registrations/1` | `scp` | FUERA_DEL_ESTANDAR | PUT /nudr-dr/v1/subscription-data/imsi-999700000000001/context-data/smf-registrations/1 no está en la API de udr |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8` | `pcf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/c041c1dc-e0fe-41f1-b1dc-7bab6a1f9cf8 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e` | `nssf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4006680-e0fe-41f1-998c-3dca3596232e no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe` | `bsf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b4b0b490-e0fe-41f1-8e2b-5b09243db5fe no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d` | `udm` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b57f81f8-e0fe-41f1-92d8-af887cb9ad1d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3` | `ausf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/b5f0ac48-e0fe-41f1-bd20-b1883afa31e3 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0` | `smf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ffd4498e-e101-41f1-88b8-a7f0377a77e0 no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d` | `udr` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/bf182d32-e0fe-41f1-a995-e5cc4cb22c3d no está en la API de scp |
| `scp` | PATCH | `/nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40` | `amf` | FUERA_DEL_ESTANDAR | PATCH /nnrf-nfm/v1/nf-instances/ea443a2a-e101-41f1-8bb2-4d905453ae40 no está en la API de scp |

## Detalle de lo observado

La tabla completa (incluidas las operaciones no observadas) está en el CSV.

| Entrada | Servicio | Método | Path | Ruta | Visto desde | Estado |
|---|---|---|---|---|---|---|
| `amf` | `callback:nnrf-nfm-status-notify` | POST | `/nnrf-nfm/v1/nf-status-notify` | directo | `scp`×2 | OBSERVADO_ORIGEN_INESPERADO |
| `amf` | `namf-comm` | POST | `/namf-comm/v1/ue-contexts/{ueContextId}/n1-n2-messages` | vía SCP | `scp`×2 | OBSERVADO_CONFORME |
| `ausf` | `nausf-auth` | POST | `/nausf-auth/v1/ue-authentications` | vía SCP | `scp`×2 | OBSERVADO_CONFORME |
| `ausf` | `nausf-auth` | PUT | `/nausf-auth/v1/ue-authentications/{authCtxId}/5g-aka-confirmation` | vía SCP | `scp`×2 | OBSERVADO_CONFORME |
| `bsf` | `nbsf-management` | POST | `/nbsf-management/v1/pcfBindings` | vía SCP | `scp`×2 | OBSERVADO_CONFORME |
| `bsf` | `nbsf-management` | DELETE | `/nbsf-management/v1/pcfBindings/{bindingId}` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `nrf` | `nnrf-disc` | GET | `/nnrf-disc/v1/nf-instances` | vía SCP | `sbi-probe`×1 | OBSERVADO_ORIGEN_INESPERADO |
| `nrf` | `nnrf-nfm` | GET | `/nnrf-nfm/v1/nf-instances` | directo | `scp`×2 | OBSERVADO_CONFORME |
| `nrf` | `nnrf-nfm` | GET | `/nnrf-nfm/v1/nf-instances/{nfInstanceID}` | directo | `scp`×22 | OBSERVADO_CONFORME |
| `nrf` | `nnrf-nfm` | PATCH | `/nnrf-nfm/v1/nf-instances/{nfInstanceID}` | directo | `scp`×181 | OBSERVADO_CONFORME |
| `nrf` | `nnrf-nfm` | PUT | `/nnrf-nfm/v1/nf-instances/{nfInstanceID}` | directo | `scp`×2 | OBSERVADO_CONFORME |
| `nrf` | `nnrf-nfm` | POST | `/nnrf-nfm/v1/subscriptions` | directo | `scp`×12 | OBSERVADO_CONFORME |
| `pcf` | `npcf-am-policy-control` | POST | `/npcf-am-policy-control/v1/policies` | vía SCP | `scp`×2 | OBSERVADO_CONFORME |
| `pcf` | `npcf-smpolicycontrol` | POST | `/npcf-smpolicycontrol/v1/sm-policies` | vía SCP | `scp`×2 | OBSERVADO_CONFORME |
| `pcf` | `npcf-smpolicycontrol` | POST | `/npcf-smpolicycontrol/v1/sm-policies/{smPolicyId}/delete` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `scp` | `callback:nnrf-nfm-status-notify` | POST | `/nnrf-nfm/v1/nf-status-notify` | directo | `nrf`×8 | OBSERVADO_CONFORME |
| `scp` | `namf-comm` | POST | `/namf-comm/v1/ue-contexts/{ueContextId}/n1-n2-messages` | vía SCP | `smf`×2 | OBSERVADO_CONFORME |
| `scp` | `nausf-auth` | POST | `/nausf-auth/v1/ue-authentications` | vía SCP | `amf`×2 | OBSERVADO_CONFORME |
| `scp` | `nausf-auth` | PUT | `/nausf-auth/v1/ue-authentications/{authCtxId}/5g-aka-confirmation` | vía SCP | `amf`×2 | OBSERVADO_CONFORME |
| `scp` | `nbsf-management` | POST | `/nbsf-management/v1/pcfBindings` | vía SCP | `pcf`×2 | OBSERVADO_CONFORME |
| `scp` | `nbsf-management` | DELETE | `/nbsf-management/v1/pcfBindings/{bindingId}` | vía SCP | `pcf`×1 | OBSERVADO_CONFORME |
| `scp` | `npcf-am-policy-control` | POST | `/npcf-am-policy-control/v1/policies` | vía SCP | `amf`×2 | OBSERVADO_CONFORME |
| `scp` | `npcf-smpolicycontrol` | POST | `/npcf-smpolicycontrol/v1/sm-policies` | vía SCP | `smf`×2 | OBSERVADO_CONFORME |
| `scp` | `npcf-smpolicycontrol` | POST | `/npcf-smpolicycontrol/v1/sm-policies/{smPolicyId}/delete` | vía SCP | `smf`×1 | OBSERVADO_CONFORME |
| `scp` | `nsmf-pdusession` | POST | `/nsmf-pdusession/v1/sm-contexts` | vía SCP | `amf`×2 | OBSERVADO_CONFORME |
| `scp` | `nsmf-pdusession` | POST | `/nsmf-pdusession/v1/sm-contexts/{smContextRef}/modify` | vía SCP | `amf`×2 | OBSERVADO_CONFORME |
| `scp` | `nsmf-pdusession` | POST | `/nsmf-pdusession/v1/sm-contexts/{smContextRef}/release` | vía SCP | `amf`×1 | OBSERVADO_CONFORME |
| `scp` | `nudm-sdm` | GET | `/nudm-sdm/v2/{supi}/am-data` | vía SCP | `amf`×2 | OBSERVADO_CONFORME |
| `scp` | `nudm-sdm` | GET | `/nudm-sdm/v2/{supi}/sm-data` | vía SCP | `smf`×2 | OBSERVADO_CONFORME |
| `scp` | `nudm-sdm` | GET | `/nudm-sdm/v2/{supi}/smf-select-data` | vía SCP | `amf`×2 | OBSERVADO_CONFORME |
| `scp` | `nudm-sdm` | GET | `/nudm-sdm/v2/{supi}/ue-context-in-smf-data` | vía SCP | `amf`×2 | OBSERVADO_CONFORME |
| `scp` | `nudm-sdm` | POST | `/nudm-sdm/v2/{ueId}/sdm-subscriptions` | vía SCP | `amf`×1, `smf`×2 | OBSERVADO_CONFORME |
| `scp` | `nudm-sdm` | DELETE | `/nudm-sdm/v2/{ueId}/sdm-subscriptions/{subscriptionId}` | vía SCP | `smf`×1 | OBSERVADO_CONFORME |
| `scp` | `nudm-ueau` | POST | `/nudm-ueau/v1/{supiOrSuci}/security-information/generate-auth-data` | vía SCP | `ausf`×2 | OBSERVADO_CONFORME |
| `scp` | `nudm-ueau` | POST | `/nudm-ueau/v1/{supi}/auth-events` | vía SCP | `ausf`×2 | OBSERVADO_CONFORME |
| `scp` | `nudm-uecm` | PUT | `/nudm-uecm/v1/{ueId}/registrations/amf-3gpp-access` | vía SCP | `amf`×2 | OBSERVADO_CONFORME |
| `scp` | `nudm-uecm` | DELETE | `/nudm-uecm/v1/{ueId}/registrations/smf-registrations/{pduSessionId}` | vía SCP | `smf`×1 | OBSERVADO_CONFORME |
| `scp` | `nudm-uecm` | PUT | `/nudm-uecm/v1/{ueId}/registrations/smf-registrations/{pduSessionId}` | vía SCP | `smf`×2 | OBSERVADO_CONFORME |
| `smf` | `callback:nnrf-nfm-status-notify` | POST | `/nnrf-nfm/v1/nf-status-notify` | directo | `scp`×2 | OBSERVADO_ORIGEN_INESPERADO |
| `smf` | `nsmf-pdusession` | POST | `/nsmf-pdusession/v1/sm-contexts` | vía SCP | `scp`×2 | OBSERVADO_CONFORME |
| `smf` | `nsmf-pdusession` | POST | `/nsmf-pdusession/v1/sm-contexts/{smContextRef}/modify` | vía SCP | `scp`×2 | OBSERVADO_CONFORME |
| `smf` | `nsmf-pdusession` | POST | `/nsmf-pdusession/v1/sm-contexts/{smContextRef}/release` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udm` | `nudm-sdm` | GET | `/nudm-sdm/v2/{supi}/am-data` | vía SCP | `scp`×2 | OBSERVADO_CONFORME |
| `udm` | `nudm-sdm` | GET | `/nudm-sdm/v2/{supi}/sm-data` | vía SCP | `scp`×2 | OBSERVADO_CONFORME |
| `udm` | `nudm-sdm` | GET | `/nudm-sdm/v2/{supi}/smf-select-data` | vía SCP | `scp`×2 | OBSERVADO_CONFORME |
| `udm` | `nudm-sdm` | GET | `/nudm-sdm/v2/{supi}/ue-context-in-smf-data` | vía SCP | `scp`×2 | OBSERVADO_CONFORME |
| `udm` | `nudm-sdm` | POST | `/nudm-sdm/v2/{ueId}/sdm-subscriptions` | vía SCP | `scp`×3 | OBSERVADO_CONFORME |
| `udm` | `nudm-sdm` | DELETE | `/nudm-sdm/v2/{ueId}/sdm-subscriptions/{subscriptionId}` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udm` | `nudm-ueau` | POST | `/nudm-ueau/v1/{supiOrSuci}/security-information/generate-auth-data` | vía SCP | `scp`×2 | OBSERVADO_CONFORME |
| `udm` | `nudm-ueau` | POST | `/nudm-ueau/v1/{supi}/auth-events` | vía SCP | `scp`×2 | OBSERVADO_CONFORME |
| `udm` | `nudm-uecm` | PUT | `/nudm-uecm/v1/{ueId}/registrations/amf-3gpp-access` | vía SCP | `scp`×2 | OBSERVADO_CONFORME |
| `udm` | `nudm-uecm` | DELETE | `/nudm-uecm/v1/{ueId}/registrations/smf-registrations/{pduSessionId}` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udm` | `nudm-uecm` | PUT | `/nudm-uecm/v1/{ueId}/registrations/smf-registrations/{pduSessionId}` | vía SCP | `scp`×2 | OBSERVADO_CONFORME |

## Limitaciones

- Los consumidores de la tabla se limitan a las NF del testbed; el estándar permite más (NEF, SMSF, LMF, CHF…).
- Las rutas de callback y su paso por el SCP están marcadas como no verificadas en `services.yaml`.
- Solo se cruzan peticiones a TCP 7777; los paths se comparan sin query string.
- Con mTLS en la SBI no hay visibilidad L7: observar siempre en modo sin TLS (ver `docs/pruebas-fase5.md`).

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
  - `fixtures/hubble/sbi-sin-tls.jsonl`

## Captura

| Métrica | Valor |
|---|---|
| Líneas leídas | 168 |
| JSON inválido | 0 |
| Flujos | 168 |
| Peticiones HTTP (L7 REQUEST) | 81 |
| Respuestas HTTP (L7 RESPONSE) | 81 |
| Flujos L3/L4 hacia TCP 7777 sin L7 | 4 |
| Flujos L3/L4 a otros puertos | 2 |
| DROPPED | 1 |
| Peticiones L7 a otros puertos (ignoradas) | 0 |

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
| OBSERVADO_CONFORME | 57 |
| OBSERVADO_ORIGEN_INESPERADO | 4 |
| NO_OBSERVADO | 594 |
| FUERA_DEL_ESTANDAR (peticiones sin operación en la API) | 1 |

## Por punto de entrada (ingress de cada NF)

| NF | Op. permitidas | Orígenes según estándar | Orígenes observados | Conformes | Origen inesperado | No observadas |
|---|---|---|---|---|---|---|
| `amf` | 19 | `nrf`, `pcf`, `scp`, `udm` | `nrf`, `pcf`, `scp` | 3 | 0 | 16 |
| `ausf` | 11 | `nrf`, `scp` | `scp` | 2 | 0 | 9 |
| `bsf` | 16 | `nrf`, `scp` | `scp` | 1 | 0 | 15 |
| `nrf` | 15 | `amf`, `ausf`, `bsf`, `nssf`, `pcf`, `scp`, `smf`, `udm`, `udr` | `?(netshoot)`, `amf`, `ausf`, `bsf`, `nssf`, `pcf`, `scp`, `smf`, `udm`, `udr` | 3 | 2 | 10 |
| `nssf` | 2 | `nrf`, `scp` | `scp` | 1 | 0 | 1 |
| `pcf` | 9 | `nrf`, `scp` | `scp` | 2 | 0 | 7 |
| `scp` | 318 | `amf`, `ausf`, `bsf`, `nrf`, `nssf`, `pcf`, `scp`, `smf`, `udm`, `udr` | `amf`, `ausf`, `nrf`, `pcf`, `smf`, `udm` | 26 | 1 | 291 |
| `smf` | 12 | `nrf`, `pcf`, `scp` | `pcf`, `scp` | 3 | 0 | 9 |
| `udm` | 74 | `nrf`, `scp` | `amf`, `scp` | 8 | 1 | 65 |
| `udr` | 179 | `nrf`, `scp` | `scp` | 8 | 0 | 171 |

## Radio de impacto por consumidor comprometido

Si un atacante toma el pod de la NF *consumidor*, ¿a cuántas operaciones de qué productores le da acceso la política? «Estándar» = política derivada del OpenAPI aplicada en la entrada del SCP. «Observado» = lo que realmente se vio hacer a esa NF. «Colapso SCP» = lo que el productor permite desde `scp`, es decir, lo que ese atacante alcanza si el SCP reenvía sin autorización propia (todo lo que el SCP puede pedir a cualquier productor).

| Consumidor | Productores (estándar) | Op. estándar | Op. observadas | Productores observados | Op. alcanzables tras colapso SCP |
|---|---|---|---|---|---|
| `amf` | `ausf`, `nrf`, `nssf`, `pcf`, `smf`, `udm` | 106 | 14 | `ausf`, `nrf`, `nssf`, `pcf`, `smf`, `udm` | 317 |
| `ausf` | `nrf`, `udm` | 22 | 3 | `nrf`, `udm` | 317 |
| `bsf` | `nrf` | 15 | 1 | `nrf` | 317 |
| `nssf` | `nrf` | 15 | 1 | `nrf` | 317 |
| `pcf` | `amf`, `bsf`, `nrf`, `udr` | 224 | 5 | `bsf`, `nrf`, `udr` | 317 |
| `scp` | `nrf` | 15 | 2 | `nrf` | 317 |
| `smf` | `amf`, `nrf`, `pcf`, `udm` | 101 | 7 | `amf`, `nrf`, `pcf`, `udm`, `udr` | 317 |
| `udm` | `amf`, `nrf`, `udr` | 209 | 7 | `nrf`, `udr` | 317 |
| `udr` | `nrf` | 15 | 1 | `nrf` | 317 |

## Hallazgos (diferencia)

### Observado desde un origen inesperado

| Entrada | Método | Path | Origen esperado | Visto desde | Motivo |
|---|---|---|---|---|---|
| `nrf` | GET | `/nnrf-disc/v1/nf-instances` | `scp` | `?(netshoot)`×1 | sin label de identidad de NF |
| `nrf` | GET | `/nnrf-nfm/v1/nf-instances` | `amf`, `ausf`, `bsf`, `nssf`, `pcf`, `scp`, `smf`, `udm`, `udr` | `?(netshoot)`×1 | sin label de identidad de NF |
| `scp` | PATCH | `/nudr-dr/v2/subscription-data/{ueId}/context-data/amf-3gpp-access` | `pcf`, `udm` | `smf`×1 | no es consumidor de este servicio según el estándar |
| `udm` | GET | `/nudm-sdm/v2/{supi}/am-data` | `scp` | `amf`×1 | consumidor legítimo pero directo, sin pasar por el SCP |

### Peticiones fuera del estándar o a destino desconocido

| Destino | Método | Path | Origen | Tipo | Detalle |
|---|---|---|---|---|---|
| `udm` | GET | `/nudm-sdm/v2/admin/dump` | `scp` | FUERA_DEL_ESTANDAR | GET /nudm-sdm/v2/admin/dump no está en la API de udm |

## Detalle de lo observado

La tabla completa (incluidas las operaciones no observadas) está en el CSV.

| Entrada | Servicio | Método | Path | Ruta | Visto desde | Estado |
|---|---|---|---|---|---|---|
| `amf` | `callback:nnrf-nfm-status-notify` | POST | `/nnrf-nfm/v1/nf-status-notify` | directo | `nrf`×1 | OBSERVADO_CONFORME |
| `amf` | `callback:npcf-am-policy-notify` | POST | `/namf-callback/v1/am-policy-notify/{polAssoId}` | directo | `pcf`×1 | OBSERVADO_CONFORME |
| `amf` | `namf-comm` | POST | `/namf-comm/v1/ue-contexts/{ueContextId}/n1-n2-messages` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `ausf` | `nausf-auth` | POST | `/nausf-auth/v1/ue-authentications` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `ausf` | `nausf-auth` | PUT | `/nausf-auth/v1/ue-authentications/{authCtxId}/5g-aka-confirmation` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `bsf` | `nbsf-management` | POST | `/nbsf-management/v1/pcfBindings` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `nrf` | `nnrf-disc` | GET | `/nnrf-disc/v1/nf-instances` | vía SCP | `?(netshoot)`×1, `scp`×6 | OBSERVADO_ORIGEN_INESPERADO |
| `nrf` | `nnrf-nfm` | GET | `/nnrf-nfm/v1/nf-instances` | directo | `?(netshoot)`×1 | OBSERVADO_ORIGEN_INESPERADO |
| `nrf` | `nnrf-nfm` | PATCH | `/nnrf-nfm/v1/nf-instances/{nfInstanceID}` | directo | `amf`×1, `pcf`×1, `smf`×1, `udm`×1 | OBSERVADO_CONFORME |
| `nrf` | `nnrf-nfm` | PUT | `/nnrf-nfm/v1/nf-instances/{nfInstanceID}` | directo | `amf`×1, `ausf`×1, `bsf`×1, `nssf`×1, `pcf`×1, `scp`×1, `smf`×1, `udm`×1, `udr`×1 | OBSERVADO_CONFORME |
| `nrf` | `nnrf-nfm` | POST | `/nnrf-nfm/v1/subscriptions` | directo | `amf`×1, `scp`×1 | OBSERVADO_CONFORME |
| `nssf` | `nnssf-nsselection` | GET | `/nnssf-nsselection/v2/network-slice-information` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `pcf` | `npcf-am-policy-control` | POST | `/npcf-am-policy-control/v1/policies` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `pcf` | `npcf-smpolicycontrol` | POST | `/npcf-smpolicycontrol/v1/sm-policies` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `scp` | `callback:nnrf-nfm-status-notify` | POST | `/nnrf-nfm/v1/nf-status-notify` | directo | `nrf`×1 | OBSERVADO_CONFORME |
| `scp` | `namf-comm` | POST | `/namf-comm/v1/ue-contexts/{ueContextId}/n1-n2-messages` | vía SCP | `smf`×1 | OBSERVADO_CONFORME |
| `scp` | `nausf-auth` | POST | `/nausf-auth/v1/ue-authentications` | vía SCP | `amf`×1 | OBSERVADO_CONFORME |
| `scp` | `nausf-auth` | PUT | `/nausf-auth/v1/ue-authentications/{authCtxId}/5g-aka-confirmation` | vía SCP | `amf`×1 | OBSERVADO_CONFORME |
| `scp` | `nbsf-management` | POST | `/nbsf-management/v1/pcfBindings` | vía SCP | `pcf`×1 | OBSERVADO_CONFORME |
| `scp` | `nnssf-nsselection` | GET | `/nnssf-nsselection/v2/network-slice-information` | vía SCP | `amf`×1 | OBSERVADO_CONFORME |
| `scp` | `npcf-am-policy-control` | POST | `/npcf-am-policy-control/v1/policies` | vía SCP | `amf`×1 | OBSERVADO_CONFORME |
| `scp` | `npcf-smpolicycontrol` | POST | `/npcf-smpolicycontrol/v1/sm-policies` | vía SCP | `smf`×1 | OBSERVADO_CONFORME |
| `scp` | `nsmf-pdusession` | POST | `/nsmf-pdusession/v1/sm-contexts` | vía SCP | `amf`×1 | OBSERVADO_CONFORME |
| `scp` | `nsmf-pdusession` | POST | `/nsmf-pdusession/v1/sm-contexts/{smContextRef}/modify` | vía SCP | `amf`×1 | OBSERVADO_CONFORME |
| `scp` | `nudm-sdm` | GET | `/nudm-sdm/v2/{supi}/am-data` | vía SCP | `amf`×1 | OBSERVADO_CONFORME |
| `scp` | `nudm-sdm` | GET | `/nudm-sdm/v2/{supi}/sm-data` | vía SCP | `smf`×1 | OBSERVADO_CONFORME |
| `scp` | `nudm-sdm` | GET | `/nudm-sdm/v2/{supi}/smf-select-data` | vía SCP | `amf`×1 | OBSERVADO_CONFORME |
| `scp` | `nudm-sdm` | GET | `/nudm-sdm/v2/{supi}/ue-context-in-smf-data` | vía SCP | `amf`×1 | OBSERVADO_CONFORME |
| `scp` | `nudm-sdm` | POST | `/nudm-sdm/v2/{ueId}/sdm-subscriptions` | vía SCP | `amf`×1 | OBSERVADO_CONFORME |
| `scp` | `nudm-ueau` | POST | `/nudm-ueau/v1/{supiOrSuci}/security-information/generate-auth-data` | vía SCP | `ausf`×1 | OBSERVADO_CONFORME |
| `scp` | `nudm-ueau` | POST | `/nudm-ueau/v1/{supi}/auth-events` | vía SCP | `ausf`×1 | OBSERVADO_CONFORME |
| `scp` | `nudm-uecm` | PUT | `/nudm-uecm/v1/{ueId}/registrations/amf-3gpp-access` | vía SCP | `amf`×1 | OBSERVADO_CONFORME |
| `scp` | `nudm-uecm` | PUT | `/nudm-uecm/v1/{ueId}/registrations/smf-registrations/{pduSessionId}` | vía SCP | `smf`×1 | OBSERVADO_CONFORME |
| `scp` | `nudr-dr` | GET | `/nudr-dr/v2/policy-data/ues/{ueId}/am-data` | vía SCP | `pcf`×1 | OBSERVADO_CONFORME |
| `scp` | `nudr-dr` | GET | `/nudr-dr/v2/policy-data/ues/{ueId}/sm-data` | vía SCP | `pcf`×1 | OBSERVADO_CONFORME |
| `scp` | `nudr-dr` | PUT | `/nudr-dr/v2/subscription-data/{ueId}/authentication-data/authentication-status` | vía SCP | `udm`×1 | OBSERVADO_CONFORME |
| `scp` | `nudr-dr` | GET | `/nudr-dr/v2/subscription-data/{ueId}/authentication-data/authentication-subscription` | vía SCP | `udm`×1 | OBSERVADO_CONFORME |
| `scp` | `nudr-dr` | PATCH | `/nudr-dr/v2/subscription-data/{ueId}/context-data/amf-3gpp-access` | vía SCP | `smf`×1 | OBSERVADO_ORIGEN_INESPERADO |
| `scp` | `nudr-dr` | PUT | `/nudr-dr/v2/subscription-data/{ueId}/context-data/amf-3gpp-access` | vía SCP | `udm`×1 | OBSERVADO_CONFORME |
| `scp` | `nudr-dr` | GET | `/nudr-dr/v2/subscription-data/{ueId}/{servingPlmnId}/provisioned-data/am-data` | vía SCP | `udm`×1 | OBSERVADO_CONFORME |
| `scp` | `nudr-dr` | GET | `/nudr-dr/v2/subscription-data/{ueId}/{servingPlmnId}/provisioned-data/sm-data` | vía SCP | `udm`×1 | OBSERVADO_CONFORME |
| `smf` | `callback:npcf-sm-policy-notify` | POST | `/nsmf-callback/v1/sm-policy-notify/{smContextRef}` | directo | `pcf`×1 | OBSERVADO_CONFORME |
| `smf` | `nsmf-pdusession` | POST | `/nsmf-pdusession/v1/sm-contexts` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `smf` | `nsmf-pdusession` | POST | `/nsmf-pdusession/v1/sm-contexts/{smContextRef}/modify` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udm` | `nudm-sdm` | GET | `/nudm-sdm/v2/{supi}/am-data` | vía SCP | `amf`×1, `scp`×1 | OBSERVADO_ORIGEN_INESPERADO |
| `udm` | `nudm-sdm` | GET | `/nudm-sdm/v2/{supi}/sm-data` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udm` | `nudm-sdm` | GET | `/nudm-sdm/v2/{supi}/smf-select-data` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udm` | `nudm-sdm` | GET | `/nudm-sdm/v2/{supi}/ue-context-in-smf-data` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udm` | `nudm-sdm` | POST | `/nudm-sdm/v2/{ueId}/sdm-subscriptions` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udm` | `nudm-ueau` | POST | `/nudm-ueau/v1/{supiOrSuci}/security-information/generate-auth-data` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udm` | `nudm-ueau` | POST | `/nudm-ueau/v1/{supi}/auth-events` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udm` | `nudm-uecm` | PUT | `/nudm-uecm/v1/{ueId}/registrations/amf-3gpp-access` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udm` | `nudm-uecm` | PUT | `/nudm-uecm/v1/{ueId}/registrations/smf-registrations/{pduSessionId}` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udr` | `nudr-dr` | GET | `/nudr-dr/v2/policy-data/ues/{ueId}/am-data` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udr` | `nudr-dr` | GET | `/nudr-dr/v2/policy-data/ues/{ueId}/sm-data` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udr` | `nudr-dr` | PUT | `/nudr-dr/v2/subscription-data/{ueId}/authentication-data/authentication-status` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udr` | `nudr-dr` | GET | `/nudr-dr/v2/subscription-data/{ueId}/authentication-data/authentication-subscription` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udr` | `nudr-dr` | PATCH | `/nudr-dr/v2/subscription-data/{ueId}/context-data/amf-3gpp-access` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udr` | `nudr-dr` | PUT | `/nudr-dr/v2/subscription-data/{ueId}/context-data/amf-3gpp-access` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udr` | `nudr-dr` | GET | `/nudr-dr/v2/subscription-data/{ueId}/{servingPlmnId}/provisioned-data/am-data` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |
| `udr` | `nudr-dr` | GET | `/nudr-dr/v2/subscription-data/{ueId}/{servingPlmnId}/provisioned-data/sm-data` | vía SCP | `scp`×1 | OBSERVADO_CONFORME |

## Limitaciones

- Los consumidores de la tabla se limitan a las NF del testbed; el estándar permite más (NEF, SMSF, LMF, CHF…).
- Las rutas de callback y su paso por el SCP están marcadas como no verificadas en `services.yaml`.
- Solo se cruzan peticiones a TCP 7777; los paths se comparan sin query string.
- Con mTLS en la SBI no hay visibilidad L7: observar siempre en modo sin TLS (ver `docs/pruebas-fase5.md`).

# Pruebas — Fase 5: spec-as-policy (`tools/spec2policy`)

Fase 5 del arco de la charla: cuando mTLS deja ciega la política L7 y el SCP colapsa
el origen, **la política se deriva del estándar 3GPP**, no de lo que se observa. Esta
guía dice qué comando correr, qué debe verse y cómo capturar flujos reales.

> **Estado de verificación.** Todo lo de esta fase está probado **en local y en CI**
> (ruff, pytest, regeneración determinista). **No se ha ejecutado contra el clúster**:
> los flujos de ejemplo son **sintéticos** (`scripts/make_fixtures.py`) y las CNP
> generadas no se han aplicado ni validado con `cilium policy`. Lo no verificado está
> marcado como tal más abajo.

## 1. Sin lab: generar y probar

```bash
make spec2policy-test   # ruff check + ruff format --check + pytest (56 tests)
make spec2policy        # regenera tools/spec2policy/examples/out/
```

Requisitos: Python ≥ 3.10 y `pip install -r tools/spec2policy/requirements.txt`
(PyYAML 6.0.2, pytest 8.3.3, ruff 0.7.4; versiones fijadas).

Qué debe verse al final de `make spec2policy`:

```
spec2policy 0.1.0 · modo standard
  servicios: 13 · filas: 655 · CNP: 10
  flujos: 168 · peticiones L7: 81 · L3/L4 a SBI sin L7: 4
  estados: NO_OBSERVADO=594, OBSERVADO_CONFORME=57, OBSERVADO_ORIGEN_INESPERADO=4
  fuera del estándar / destino desconocido: 1
  -> examples/out/cnp/spec2policy-sbi-amf.yaml
  ...
  -> examples/out/blast-radius-map.md
  -> examples/out/blast-radius-map.csv
```

Y en `examples/out/`:

| Fichero | Qué es |
|---|---|
| `cnp/spec2policy-sbi-{amf,ausf,bsf,nrf,nssf,pcf,scp,smf,udm,udr}.yaml` | Una CNP de ingress SBI por NF, con `rules.http` por método y path (regex) agrupadas por NF origen. Usan los mismos selectores que `cilium-policies/` (`app.kubernetes.io/name`, `app.kubernetes.io/instance: open5gs-cp`, ns `5g-cp`, TCP 7777). |
| `cnp/spec2policy-sbi-l7-visibility.yaml` | CNP que fuerza el proxy L7 en 7777 para poder capturar (ver §3). |
| `blast-radius-map.md` | El informe que se lleva la audiencia. |
| `blast-radius-map.csv` | Lo mismo, una fila por operación, para filtrar en hoja de cálculo. |

En el informe de ejemplo deben aparecer los **4 hallazgos sembrados** en los flujos
sintéticos:

1. Pod `netshoot` (sin etiqueta de NF) haciendo `GET /nnrf-nfm/v1/nf-instances` y
   `GET /nnrf-disc/v1/nf-instances` al NRF → `OBSERVADO_ORIGEN_INESPERADO`.
2. `amf` → `udm` **directo** `GET /nudm-sdm/v2/{supi}/am-data` saltándose el SCP →
   `OBSERVADO_ORIGEN_INESPERADO` en el ingress del UDM.
3. `smf` → `scp` → `udr` `PATCH /nudr-dr/v2/subscription-data/{ueId}/context-data/amf-3gpp-access`:
   el SMF no es consumidor de `nudr-dr`. Solo es detectable en el **ingress del SCP**;
   en el UDR llega desde `scp` y queda como `OBSERVADO_CONFORME`. Este es el punto
   de la «trampa» del SCP (§4).
4. `scp` → `udm` `GET /nudm-sdm/v2/admin/dump` (404): no existe en el OpenAPI →
   `FUERA_DEL_ESTANDAR`.

La CI (`.github/workflows/ci.yml`, job `spec2policy`) ejecuta lint, tests y comprueba
que `examples/out/` coincide con lo regenerado; si cambias el modelo o las fixtures,
corre `make spec2policy` y commitea la salida.

## 2. Con lab: aplicar la política derivada (NO verificado)

```bash
kubectl apply -f tools/spec2policy/examples/out/cnp/spec2policy-sbi-l7-visibility.yaml
kubectl apply -f tools/spec2policy/examples/out/cnp/   # las 10 CNP de ingress
cilium policy get | head                                # o: kubectl get cnp -n 5g-cp
kubectl -n 5g-ran logs deploy/ueransim-ue | tail        # el UE debe seguir registrándose
```

Las CNP de `spec2policy` son **aditivas** a las de `k8s/cilium/` (etiqueta
`app.kubernetes.io/part-of: spec2policy`); Cilium une los permisos de todas las políticas
que seleccionan un endpoint, así que para medir el efecto real hay que retirar antes las
reglas L7 equivalentes del lab (`k8s/cilium/base/02-nrf-sbi-l7.yaml`) o aplicarlas en un
clúster limpio.
Pendiente de probar: que el regex `(\?.*)?` y `[^/?]+` casen como se espera en el Envoy
de Cilium 1.15.4 y que Open5GS 2.7.5 use las mismas versiones de API que Rel-17 (en
particular `/nudr-dr/v2`; si usa `/nudr-dr/v1`, saldrá como `FUERA_DEL_ESTANDAR`).

## 3. Capturar flujos reales con visibilidad L7 (Cilium 1.15)

Hubble solo emite campos `l7.http` cuando el tráfico pasa por el proxy Envoy de Cilium.
En 1.15 hay dos formas de conseguirlo:

- **Regla L7 en una CNP** (recomendada; la anotación `policy.cilium.io/proxy-visibility`
  está *deprecated* en 1.15 y desaparece en 1.16). Basta una regla `http: [{}]` sobre
  TCP 7777 que no restringe nada pero redirige al proxy:

  ```bash
  python -m spec2policy visibility --out visibility.yaml   # desde tools/spec2policy
  kubectl apply -f visibility.yaml
  ```

- **Anotación** (alternativa, deprecated):
  `kubectl -n 5g-cp annotate pod -l app.kubernetes.io/instance=open5gs-cp policy.cilium.io/proxy-visibility="<Ingress/7777/TCP/HTTP>"`.

Después, captura los flujos mientras generas tráfico:

```bash
hubble observe --namespace 5g-cp -f -o jsonpb > capturas/sbi_$(date -u +%Y%m%dT%H%M%SZ).jsonl &
# ... registrar el UE, levantar una sesión PDU, etc. ...
kill %1
cd tools/spec2policy
python -m spec2policy inspect-flows ../../capturas/*.jsonl       # ¿hay l7_req > 0?
python -m spec2policy generate --flows ../../capturas/*.jsonl --out ../../results/fase5
```

`inspect-flows` imprime `flujos=… l7_req=… l34_sbi=…`. Si `l7_req=0` y `l34_sbi>0`,
no hay visibilidad: o no está el proxy (§3) o hay mTLS (§5).

El parser lee de cada flujo `l7.http.method`, `l7.http.url`, `l7.type`
(REQUEST/RESPONSE), `source`/`destination` (`pod_name`, `namespace`, `labels`), el
puerto destino L4 y el `verdict`. Las NF se identifican por la etiqueta
`app.kubernetes.io/name`, la misma que usa el chart de Gradiant y las CNP del repo. Los
pods sin esa etiqueta aparecen como `?(<pod>)` en el informe (así se ve el `netshoot`).

## 4. Efecto del SCP (comunicación indirecta)

Open5GS 2.7.5 despliega un **SCP** y las NF le delegan el enrutado (modelo D de
TS 23.501 Anexo E). Consecuencias que el informe hace explícitas:

- En el ingress de **cada productor** casi todo llega con origen `scp`. Una política
  por consumidor en el productor **no puede** distinguir AMF de SMF: solo puede decir
  «del SCP, estas operaciones».
- La autorización **por consumidor** se desplaza al **ingress del SCP**: allí sí se ve
  qué NF pide qué. Por eso `spec2policy` genera cada operación dos veces (fila en el
  productor con origen `scp` y fila en el SCP con los consumidores del estándar) y la CNP
  del SCP es la más grande (318 operaciones permitidas en el ejemplo).
- Excepción: `nnrf-nfm` (registro, heartbeat, suscripciones) va **directo** al NRF.
- Columna «Op. alcanzables tras colapso SCP» del informe: si el SCP reenvía sin
  autorización propia, un pod comprometido alcanza *todo* lo que el SCP puede pedir a
  cualquier productor. Ese número (317 en el ejemplo) es el argumento de la charla.

No verificado: cómo enruta Open5GS los **callbacks** (notificaciones NRF→NF,
UDM→AMF, SMF→AMF). `services.yaml` los modela como directos; si van vía SCP, aparecerán
como `OBSERVADO_ORIGEN_INESPERADO` desde `scp` y habrá que cambiar `route` en la tabla.

## 5. mTLS: sin visibilidad L7

Con mTLS en la SBI (TS 33.501 §13.1; en Open5GS, `sbi.server.tls` / `sbi.client.tls`),
Cilium **no puede** inspeccionar HTTP: Hubble solo emite L3/L4 hacia 7777 y la política
L7 **no se puede aplicar ni verificar**. El informe lo detecta (tráfico SBI sin ninguna
petición HTTP) y muestra el aviso correspondiente; `--mode observed` aborta.

Procedimiento: **observar en modo sin TLS** (configuración por defecto del chart) para
construir el blast radius map; después activar mTLS. Lo que queda vigente con mTLS es la
política **derivada del estándar** (`--mode standard`) aplicada en la identidad
(L3/L4), más el corte en el kernel de la fase siguiente (Tetragon). Ejemplo del aviso con
la fixture `sbi-mtls-sin-l7.jsonl`:

```
flujos=33 l7_req=0 l7_resp=0 l34_sbi=32 l34_otros=1 dropped=0
AVISO: hay tráfico SBI pero ninguna petición HTTP visible (¿mTLS activo?).
```

## 6. Plantilla del blast radius map

Para la versión «real» del mapa (capturada en el clúster), rellena
`docs/blast-radius-map-plantilla.md` y `docs/blast-radius-map-plantilla.csv` a partir de
la salida de `generate` sobre los flujos reales; la versión sintética de ejemplo está en
`tools/spec2policy/examples/out/`.

## 7. Resumen de lo no verificado

| Punto | Estado |
|---|---|
| Flujos de ejemplo | Sintéticos; generados por `scripts/make_fixtures.py` |
| CNP aplicadas en el clúster | No probado |
| Semántica del regex en Envoy/Cilium 1.15.4 | No probado |
| Visibilidad L7 sobre HTTP/2 cleartext (Open5GS) | No probado en este repo |
| Versiones de API de Open5GS 2.7.5 vs Rel-17 (`nudr-dr` v1/v2) | No comprobado |
| Enrutado de callbacks vía SCP en Open5GS | No comprobado |
| Comportamiento con mTLS | Modelado con fixture sintética, no capturado |

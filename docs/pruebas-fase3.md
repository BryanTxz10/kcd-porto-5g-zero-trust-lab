# Pruebas — Fase 3: Cilium para lo que queda en la red de pods

Con redes dedicadas, N2, N3 y N6 salen de Cilium (Fase 1) y sus controles son los de
la Fase 2. En la red de pods quedan la SBI, N4, MongoDB, el DNS y la radio simulada
(RLS UE↔gNB): eso es lo que protege Cilium en esta fase, en los dos modos del
interruptor `deploy_multus`.

> **Estado de verificación.** `make policy-matrix` (aproximación L3/L4, sin clúster)
> da lo esperado en los dos modos, y los dos overlays construyen con kustomize. Pasan
> yamllint, `ansible-lint` y `--syntax-check`. **No se ha aplicado en un clúster**:
> ni las políticas, ni WireGuard, ni la combinación L7 + WireGuard.

## 1. Qué se aplica

`k8s/cilium/` (detalle en su [`README.md`](../k8s/cilium/README.md)):

| | Plan B (`una-red/`) | Redes dedicadas (`multus/`) |
|---|---|---|
| Default deny de ingress y egress en 5g-cp, 5g-ran y 5g-up | ✔ | ✔ |
| SBI (TCP 7777) solo entre identidades de NF (`app.kubernetes.io/name` + `instance=open5gs-cp`) | ✔ | ✔ |
| NRF con L7: solo operaciones de TS 29.510 | ✔ | ✔ |
| N4 solo SMF → UPF (UDP 8805) | ✔ | ✔ |
| MongoDB solo desde UDR, PCF y populate | ✔ | ✔ |
| 5g-cp sin `world` | ✔ | ✔ |
| RLS UE↔gNB dentro de 5g-ran | ✔ | ✔ |
| N2 gNB → AMF (SCTP 38412) | ✔ | — (Multus, Fase 2) |
| N3 gNB ↔ UPF (UDP 2152) | ✔ | — (Multus, Fase 2) |
| UPF → `world` (N6) | ✔ | — : sale por `n6`; **egress del UPF en la red de pods vacío** |

El playbook aplica el overlay del modo al final (`--tags policies`, variable
`apply_cilium_policies`) con `kubectl apply --prune -l kcd.io/policy-set=lab`, de
modo que al cambiar de modo se borran las reglas que sobran (p. ej. las de N2/N3/N6
al pasar a Multus). A mano: `make policies` (elige el modo leyendo
`group_vars/all.yml`) o `make policies MODE=una-red|multus`.

## 2. Sin clúster: la matriz

```bash
make policy-matrix
```

Debe terminar en `OK: todos los flujos dan lo esperado en los dos modos`. Para cada
flujo muestra el veredicto en `una-red` y en `multus`. `Multus [DROP(egress)]`
significa: en ese modo el flujo va por una interfaz de Multus y, si alguien lo
intentara por la red de pods, Cilium lo descartaría. El CI la ejecuta y falla si un
flujo no da lo esperado.

## 3. En el clúster (no ejecutado aún)

### 3.1 Políticas aplicadas y válidas

```bash
kubectl get cnp -A -l kcd.io/policy-set=lab
kubectl get cnp -A -l kcd.io/policy-mode=multus      # o una-red: debe coincidir con deploy_multus
```

### 3.2 Lo legítimo sigue funcionando

```bash
make ran-restart
kubectl -n 5g-ran exec deploy/ueransim-ues -- ip -br a show uesimtun0   # registro + sesión PDU
kubectl -n 5g-ran exec deploy/ueransim-ues -- ping -c3 -I uesimtun0 8.8.8.8
hubble observe -n 5g-cp --verdict DROPPED --last 50     # no debe haber drops entre NF legítimas
```

### 3.3 Lo que debe caer, con Hubble

```bash
kubectl apply -f attacks/attacker-ran.yaml      # atacante en 5g-ran
kubectl -n 5g-ran exec attacker-ran -- \
  curl -s -m 3 http://open5gs-cp-nrf-sbi.5g-cp.svc.cluster.local:7777/nnrf-disc/v1/nf-instances || echo bloqueado
hubble observe --from-pod 5g-ran/attacker-ran --verdict DROPPED --last 20
#   ... 5g-ran/attacker-ran -> 5g-cp/open5gs-cp-nrf-... Policy denied DROPPED (TCP Flags: SYN)
```

En modo Multus, además, el UPF no sale a `world` por la red de pods:

```bash
hubble observe --from-label app.kubernetes.io/name=upf --to-identity world --last 20   # vacío o DROPPED; N6 va por n6
```

### 3.4 L7 en el NRF

Desde el pod de prueba `sbi-probe` (solo puede hacer `GET /nnrf-disc/v1/nf-instances`),
una ruta distinta recibe 403 del proxy de Cilium, no del NRF:

```bash
make demo-l7-ciega        # GET /nnrf-nfm/v1/nf-instances desde sbi-probe
#   http_code=403
hubble observe -n 5g-cp --protocol http --last 20      # método, ruta y el 403
```

No se hace desde dentro del AMF: en la Fase 6 Tetragon mata las herramientas de red
que se ejecuten en él.

### 3.5 WireGuard entre nodos (`node_encryption: true`)

```bash
# en group_vars: node_encryption: true
ansible-playbook site.yml -K --tags cilium,policies
kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg encrypt status
#   Encryption: Wireguard ... Peers: 2 (o 3)
# N4 y SBI cifrados entre worker1 y worker2: en un worker, durante un registro
sudo tcpdump -ni ens33 udp port 51871 -c 20      # tráfico WireGuard entre nodos
sudo tcpdump -ni ens33 udp port 8805 -c 5        # PFCP en claro: no debe aparecer
```

Comprueba después que **L7 sigue funcionando con WireGuard** repitiendo §3.4: el 403
y los eventos HTTP en Hubble deben seguir apareciendo. Si no, déjalo anotado y no
afirmes en la charla que conviven.

## 4. Supuestos sin verificar

| Supuesto | Si falla |
|---|---|
| Las etiquetas `app.kubernetes.io/name` e `instance` de los pods son las que usa la política (`amf`, `scp`, … e `instance=open5gs-cp`) | Drops entre NF legítimas: `kubectl get pods -n 5g-cp --show-labels` y ajustar `base/01` y `base/02` |
| Open5GS 2.7 solo usa las operaciones de la lista en el NRF (registro, heartbeat, discovery, suscripciones, `oauth2/token`) | 403 legítimos en Hubble: añadir la ruta a `base/02-nrf-sbi-l7.yaml` |
| Las respuestas y heartbeats PFCP del UPF vuelven por conntrack (mismo par de puertos 8805) | La asociación PFCP se cae: permitir egress UPF → SMF UDP 8805 en `base/05-n4.yaml` |
| El UPF no necesita DNS ni ninguna otra salida por la red de pods en modo Multus | El UPF no arranca o no asocia: mirar `hubble observe --from-label app.kubernetes.io/name=upf --verdict DROPPED` |
| `kubectl apply --prune --prune-allowlist` funciona con CNP en kubectl 1.28 | Borrar a mano las del otro modo: `kubectl delete cnp -A -l kcd.io/policy-mode=<otro>` y reaplicar |
| L7 y WireGuard conviven en Cilium 1.15.4 | Ver §3.5 |

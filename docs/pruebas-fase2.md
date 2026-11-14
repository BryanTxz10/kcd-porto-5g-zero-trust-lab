# Pruebas — Fase 2: controles en las redes dedicadas

Con `deploy_multus: true`, N2, N3 y N6 viajan por interfaces de Multus que **Cilium
no ve ni filtra** (Fase 1). Esta fase pone los controles que usa un operador en esas
redes, en tres capas:

| Capa | Qué decide | Dónde | Cuándo actúa |
|---|---|---|---|
| **1. Aislamiento L2** | Qué VMs comparten red | LAN segments `ACCESS` y `N6` de VMware (equivalen a una VLAN o VRF) | siempre |
| **2. Admisión (Kyverno)** | Qué pod puede *pedir* `access` o `n6`, con qué IP y qué interfaz | API server, ClusterPolicy `kcd-multus-network-guard` | al crear el pod |
| **3. MultiNetworkPolicy** | Qué tráfico pasa por esas interfaces | `multi-networkpolicy-iptables`, iptables dentro del netns del pod | en cada paquete |

La frase de la charla: **conectarse a la red de la radio es una decisión de
admisión, no de red.**

> **Estado de verificación.** Pasan yamllint, `ansible-lint` y `--syntax-check`.
> Se probaron en local los ajustes que el playbook hace al manifiesto de
> multi-networkpolicy-iptables (contra un manifiesto de ejemplo) y la extracción de
> la política de admisión. **Nada de esta fase se ha ejecutado en un clúster**: ni
> Kyverno, ni la política, ni las MultiNetworkPolicy. El tag
> `multi_networkpolicy_version` y el soporte de ipvlan y SCTP están **sin
> comprobar** (§4).

## 1. Qué despliega el playbook (solo con `deploy_multus: true`)

| Pieza | Versión / fichero | Tag |
|---|---|---|
| Kyverno | chart 3.1.4 (Kyverno 1.11.4, K8s 1.25–1.28) | `admission` |
| ClusterPolicy `kcd-multus-network-guard` | `bootstrap/admission/kyverno-identity-guard.yaml` (2.º documento) | `admission` |
| multi-networkpolicy-iptables | `multi_networkpolicy_version` (⚠ tag por verificar), con `--network-plugins=ipvlan` y el socket de containerd de k3s | `mnp` |
| MultiNetworkPolicy | `multinetwork-policies/` | `mnp` |

El playbook aplica **solo** el documento de redes dedicadas. El otro ClusterPolicy
del fichero (`cib46-identity-guard`, de la tesis) sigue siendo manual porque su
allowlist hay que ajustarla al clúster. Antes de aplicar, el playbook comprueba que
las IP de la política coinciden con `group_vars/all.yml`.

Si la política bloquea algo legítimo la primera vez, pon
`kyverno_multus_guard_action: Audit`, relanza con `--tags admission` y mira
`kubectl get policyreport -A`.

### Reglas de admisión

| Regla | Rechaza |
|---|---|
| `anotacion-en-formato-json` | la forma corta `access,n6` (no se puede inspeccionar) |
| `redes-dedicadas-solo-en-el-core` | cualquier pod fuera de 5g-cp, 5g-ran y 5g-up que pida una red de Multus |
| `sin-referencias-a-otro-namespace` | pedir el NAD de otro namespace (`"namespace": "5g-up"` desde 5g-ran) |
| `solo-pods-de-un-controlador` | un Pod creado directamente, aunque copie etiquetas e IP |
| `access-en-5g-cp-solo-amf` | en 5g-cp, todo lo que no sea el AMF con `access`, interfaz `n2`, 10.10.0.10/24 |
| `access-en-5g-ran-solo-gnb` | en 5g-ran, todo lo que no sea el gNB con `access`, interfaz `access`, 10.10.0.20/24 |
| `access-y-n6-en-5g-up-solo-upf` | en 5g-up, todo lo que no sea el UPF con `access` (`n3`, 10.10.0.30/24) y `n6` (`n6`, 10.10.6.30/24) |

**Alcance.** La admisión decide *qué pide* un pod, no *quién es* el administrador.
Quien tenga credenciales de administrador puede crear un Deployment con las
etiquetas del AMF, y sus pods pasarán. Eso lo cubre RBAC (y la firma de imágenes en
la cadena de suministro), no este control. Se dice así en la charla.

### MultiNetworkPolicy

| Red | Pod | Entra | Sale |
|---|---|---|---|
| access | AMF (10.10.0.10) | SCTP 38412 desde 10.10.0.20 | solo hacia 10.10.0.20 |
| access | gNB (10.10.0.20) | SCTP 38412 desde 10.10.0.10; UDP 2152 desde 10.10.0.30 | SCTP 38412 → AMF; UDP 2152 → UPF |
| access | UPF (10.10.0.30) | UDP 2152 desde 10.10.0.20 | UDP 2152 → 10.10.0.20 |
| n6 | UPF (10.10.6.30) | dn-gw y destinos públicos | dn-gw y destinos públicos; nunca rangos privados |
| access, n6 | cualquier otro pod | nada (default deny) | nada |

dn-gw aplica en su lado el mismo criterio para N6: desde el pool de UE no se
alcanzan redes privadas (Fase 1).

## 2. Mapeo a TS 33.501

| Interfaz | TS 33.501 | Qué pide | Qué hace este lab |
|---|---|---|---|
| N2 (gNB↔AMF) | §9.2 | Protección de confidencialidad, integridad y anti-replay; IPsec (NDS/IP, TS 33.210) **obligatorio de implementar, opcional de usar**; DTLS también posible | Aislamiento L2, admisión y MultiNetworkPolicy. **Sin IPsec ni DTLS: fuera de alcance**, se declara |
| N3 (gNB↔UPF) | §9.3 | Igual: IPsec obligatorio de implementar, opcional de usar | Igual que N2. Sin IPsec, se declara |
| N4 (SMF↔UPF) | §9.9 (interfaces internas no SBA) | Protección según NDS/IP | Fase 3: va por Cilium (identidad, solo SMF→UPF) y, con `node_encryption: true`, cifrado WireGuard entre nodos |
| N6 | — (fuera del core) | — | CGNAT y firewall en dn-gw, MultiNetworkPolicy en el UPF |

## 3. Qué comprobar y qué debe verse (no ejecutado aún)

### 3.1 Admisión: la demo

```bash
kubectl get clusterpolicy kcd-multus-network-guard          # READY True

# Un atacante pide la red de la radio
kubectl apply -f attack-scripts/deploy-attacker-access.yaml
# Debe verse, para los dos pods, algo como:
#   Error from server: admission webhook "validate.kyverno.svc-fail" denied the request:
#   policy Pod/5g-ran/attacker-access for resource violation:
#   kcd-multus-network-guard:
#     access-en-5g-ran-solo-gnb: En 5g-ran solo el gNB puede pedir la red 'access' ...
#     solo-pods-de-un-controlador: Un Pod creado directamente no puede pedir redes dedicadas ...

kubectl -n 5g-ran get pod attacker-access attacker-access-gnb-label   # NotFound

# Los legítimos siguen arriba
kubectl -n 5g-cp  get pod -l app.kubernetes.io/name=amf
kubectl -n 5g-up  get pod -l app.kubernetes.io/name=upf
kubectl -n 5g-ran get pod -l app.kubernetes.io/name=ueransim-gnb
```

El mensaje exacto del webhook depende de la versión de Kyverno: copia el que salga
en el lab, no este.

### 3.2 MultiNetworkPolicy

```bash
kubectl -n kube-system get ds -l app=multi-networkpolicy      # o el nombre que traiga deploy.yml
kubectl get multi-networkpolicies -A

# Reglas generadas dentro del netns de un pod (en el worker donde corre):
#   PID=$(crictl inspect $(crictl ps --name upf -q) | jq .info.pid)
#   sudo nsenter -t "$PID" -n iptables-save | grep -i multi
# Debe haber reglas para n3 (UDP 2152 con 10.10.0.20) y n6.

# Desde el gNB, tráfico permitido y no permitido por access:
kubectl -n 5g-ran exec deploy/ueransim-gnb -- ping -c2 -I access 10.10.0.10   # no permitido: sin respuesta
kubectl -n 5g-ran logs deploy/ueransim-gnb | grep 'NG Setup'                   # permitido: sigue OK

# El UE sigue navegando (N3 y N6 permitidos)
kubectl -n 5g-ran exec deploy/ueransim-ues -- ping -c3 -I uesimtun0 8.8.8.8
```

### 3.3 Lo que la política no hace (para la charla)

- **Un gNB comprometido sí pasa.** La MultiNetworkPolicy permite el origen
  10.10.0.20 hacia el AMF, así que un gNB comprometido puede abrir tantas
  asociaciones NGAP como quiera. **La política decide quién, no cuánto.** El
  escenario A3 desde el gNB se ejecuta con el script existente
  (`attack-scripts/run_a3_n2_flood.sh`), adaptado al pod del gNB.
- **Un UE contra el core.** Desde `uesimtun0`, cualquier intento hacia la SBI o la red
  del clúster sale por N6 y muere en dn-gw: no toca la red de pods.

  ```bash
  kubectl -n 5g-ran exec deploy/ueransim-ues -- \
    curl -s -m 3 --interface uesimtun0 http://10.43.0.10:53 || echo bloqueado
  # en dn-gw, a la vez:
  sudo tcpdump -ni n6 'src net 10.45.0.0/16 and dst net 10.0.0.0/8'   # se ve el intento
  sudo iptables -L DN-N6-FWD -v -n                                     # sube el contador de DROP
  ```

## 4. Supuestos sin verificar y huecos

| Supuesto | Si falla |
|---|---|
| El tag `v0.2.0` de multi-networkpolicy-iptables existe (manifiesto e imagen) | El playbook falla al descargar o el pod queda en `ImagePullBackOff`: cambia `multi_networkpolicy_version` |
| `--network-plugins=ipvlan` hace que gestione las interfaces ipvlan | Sin reglas en el netns: `deploy_multi_networkpolicy: false` y quedarse con L2 + admisión |
| Soporta `protocol: SCTP` | Las reglas de N2 no se generan o descartan NGAP: documentar el hueco y quitar el puerto SCTP |
| Las respuestas pasan por conntrack (reglas con estado) | Si no, hacen falta reglas simétricas de entrada y salida |
| Filtra también lo que el UPF **reenvía** por n6 (tráfico de los UE), no solo lo que el pod envía o recibe | Si solo filtra INPUT/OUTPUT, en n6 manda dn-gw (que sí filtra FORWARD) |
| En k3s los pods de un Deployment se crean como `system:kube-controller-manager` o como la SA del controlador | Si es otro usuario, `solo-pods-de-un-controlador` rechaza a los legítimos: modo `Audit` y añadirlo |
| Kyverno 1.11 admite `operations` en `match` y `parse_json` en las condiciones | La política no pasa a Ready: `kubectl describe clusterpolicy kcd-multus-network-guard` |

Si multi-networkpolicy-iptables no sirve con ipvlan o SCTP, el plan es el que
pide la consigna: **admisión + L2**, con el hueco documentado.

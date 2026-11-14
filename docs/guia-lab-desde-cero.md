# Montar el lab desde cero

Esta guía lleva de un laptop con VMware Workstation a un core 5G SA (Open5GS) en
Kubernetes con un UE navegando, y después a cada una de las piezas de la demo:
redes dedicadas, admisión, políticas de Cilium, mTLS en la SBI y Tetragon. Todo lo
que pasa dentro de las VMs lo hace Ansible; a mano solo se crean las VMs.

> **Estado.** El playbook y las políticas pasan las comprobaciones estáticas del CI
> (yamllint, ansible-lint, kustomize, shellcheck, matriz de políticas), pero esta
> versión del lab todavía no se ha desplegado de punta a punta. Cada
> `docs/pruebas-faseN.md` indica qué está comprobado y qué no.

## Índice

0. [Qué vas a construir](#0-qué-vas-a-construir)
1. [Requisitos](#1-requisitos)
2. [VMs y redes](#2-vms-y-redes)
3. [Ansible en el nodo de control](#3-ansible-en-el-nodo-de-control)
4. [Los interruptores](#4-los-interruptores)
5. [Primer despliegue: una sola red](#5-primer-despliegue-una-sola-red)
6. [Comprobar que el core funciona](#6-comprobar-que-el-core-funciona)
7. [Endurecer el clúster y guardar un snapshot](#7-endurecer-el-clúster-y-guardar-un-snapshot)
8. [Redes dedicadas (Multus)](#8-redes-dedicadas-multus)
9. [mTLS en la SBI](#9-mtls-en-la-sbi)
10. [Cifrado entre nodos (WireGuard)](#10-cifrado-entre-nodos-wireguard)
11. [Tetragon](#11-tetragon)
12. [Captura para el blast radius map](#12-captura-para-el-blast-radius-map)
13. [Apagar y volver a encender](#13-apagar-y-volver-a-encender)
14. [Problemas frecuentes](#14-problemas-frecuentes)
15. [Referencia: tags del playbook](#15-referencia-tags-del-playbook)

---

## 0. Qué vas a construir

```
                     Laptop · VMware Workstation
   mgmt = VMnet8 (NAT) 192.168.100.0/24 · pods 10.42.0.0/16 (VXLAN) · Services 10.43.0.0/16
   ─────┬──────────────────────┬──────────────────────────┬──────────────────┬──────────
        │.10                   │.11                       │.12               │.13
 ┌──────┴──────┐  ┌────────────┴────────────┐  ┌──────────┴──────────┐  ┌────┴─────────┐
 │ node-master │  │ node-worker1            │  │ node-worker2        │  │ dn-gw        │
 │ k3s server  │  │ SITIO CENTRAL           │  │ SITIO DE BORDE      │  │ RED DE DATOS │
 │ con taint   │  │ 5g-cp: NRF SCP AMF SMF  │  │ 5g-up: UPF          │  │ router N6    │
 │             │  │ AUSF UDM UDR PCF NSSF   │  │ 5g-ran: gNB, UE,    │  │ CGNAT +      │
 │             │  │ BSF, MongoDB            │  │ atacantes           │  │ firewall N6  │
 └─────────────┘  └────────────┬────────────┘  └───┬────────────┬────┘  └────┬─────────┘
                    AMF n2 .10 │          gNB .20  │  UPF n3 .30│ UPF n6 .30 │ n6 .1
   access 10.10.0.0/24 ────────┴───────────────────┘            │            │
   (N2 NGAP/SCTP + N3 GTP-U)                                    │            │
   n6 10.10.6.0/24 ─────────────────────────────────────────────┴────────────┘
   (tráfico de los UE hacia la red de datos)                       pool UE 10.45.0.0/16
```

Hay dos formas de desplegarlo, según el interruptor `deploy_multus`:

| | `deploy_multus: false` (una red) | `deploy_multus: true` (redes dedicadas) |
|---|---|---|
| VMs | master y dos workers (dn-gw puede quedarse apagada) | las cuatro |
| N2, N3 y N6 | por la red de pods, bajo Cilium | por interfaces de Multus en `access` y `n6` |
| Para qué | punto de partida y plan B | la arquitectura de la charla |

La guía despliega primero con una red y luego activa el resto. Así, si algo falla
después, se sabe que el core funcionaba. Por qué está diseñado así y en qué se
parece a un operador: [`arquitectura.md`](arquitectura.md).

## 1. Requisitos

| | Mínimo |
|---|---|
| RAM libre en el laptop | 14 GB (12 GB bajando los workers a 4 GB) |
| Disco libre | unos 130 GB (los discos de VMware crecen según se usan) |
| CPU | 7 vCPU entre las cuatro VMs; virtualización activada en la BIOS |
| Hipervisor | VMware Workstation Pro 17 |
| SO de las VMs | Ubuntu Server 22.04.5 LTS (amd64) |
| Red | salida a internet desde el laptop: el playbook descarga k3s, charts e imágenes |

Versiones que fija el playbook (`ansible/group_vars/all.yml`):

| Componente | Versión |
|---|---|
| k3s | v1.28.5+k3s1 |
| Cilium | 1.15.4 (kube-proxy replacement, VXLAN, Hubble) |
| Open5GS | 2.7.5 (chart OCI de Gradiant 2.3.4) |
| UERANSIM | v3.2.6 |
| Multus | v4.0.2 (thick) |
| Kyverno | chart 3.1.4 |
| Tetragon | chart 1.1.2 |

## 2. VMs y redes

Sigue [`guia-vms-realista.md`](guia-vms-realista.md) de principio a fin. Cubre los LAN
segments `ACCESS` y `N6`, la VM plantilla, los clones, las NIC de cada VM, el netplan
con los nombres de interfaz fijados por MAC y el inventario de Ansible.

Al terminar debe cumplirse esto:

- Las cuatro VMs responden por SSH en 192.168.100.10 a .13 con el mismo usuario (en
  esta guía, `bryantxz10`; si usas otro, cámbialo en
  `ansible/inventory/hosts.ini`).
- En los workers existen las interfaces `access` (y `n6` en `node-worker2`), sin IP.
- En `dn-gw`, `n6` tiene 10.10.6.1/24.
- Hay un snapshot `fase0-redes-ok` de cada VM.

Si solo vas a usar el modo de una red, basta con el master y los dos workers con su
NIC de `mgmt`.

## 3. Ansible en el nodo de control

El nodo de control es `node-master`: Ansible se instala ahí y desde ahí configura
todas las VMs, él incluido. También vale un Linux o un WSL2 en el laptop que llegue
a 192.168.100.0/24.

En `node-master`:

```bash
sudo apt update
sudo apt install -y software-properties-common git make python3-yaml
sudo add-apt-repository --yes --update ppa:ansible/ansible
sudo apt install -y ansible
ansible --version
```

Llave SSH hacia las cuatro VMs (pide la contraseña una vez por VM, también la del
propio master):

```bash
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
for h in 192.168.100.10 192.168.100.11 192.168.100.12 192.168.100.13; do
  ssh-copy-id -o StrictHostKeyChecking=accept-new bryantxz10@$h
done
```

El repo:

```bash
git clone https://github.com/BryanTxz10/kcd-porto-5g-zero-trust-lab.git
cd kcd-porto-5g-zero-trust-lab/ansible
ansible-inventory --graph        # @cluster (master, workers) y @dn
ansible all -m ping              # SUCCESS en las cuatro (o en tres si dn-gw está apagada)
```

Con `deploy_multus: false` puedes comentar `dn-gw` en `inventory/hosts.ini` si está
apagada; el play de dn-gw no se conecta en ese modo, pero `ansible all -m ping` sí.

## 4. Los interruptores

Todo se controla desde `ansible/group_vars/all.yml`:

| Variable | Por defecto | Qué activa | Pruebas |
|---|---|---|---|
| `deploy_multus` | `false` | redes dedicadas `access` y `n6`, dn-gw, Kyverno y MultiNetworkPolicy | [fase 1](pruebas-fase1.md), [fase 2](pruebas-fase2.md) |
| `deploy_multi_networkpolicy` | `true` | MultiNetworkPolicy en las redes dedicadas (solo con Multus) | [fase 2](pruebas-fase2.md) |
| `kyverno_multus_guard_action` | `Enforce` | `Audit` para observar sin bloquear | [fase 2](pruebas-fase2.md) |
| `apply_cilium_policies` | `true` | políticas de Cilium del modo elegido al final del despliegue | [fase 3](pruebas-fase3.md) |
| `node_encryption` | `false` | WireGuard entre nodos | [fase 3](pruebas-fase3.md) |
| `sbi_tls` | `false` | mTLS en la SBI con una CA propia generada en el master | [fase 4](pruebas-fase4.md) |
| `deploy_tetragon` | `true` | Tetragon y sus políticas | [fase 6](pruebas-fase6.md) |

Orden recomendado: todo como viene, comprobar, y luego activar de uno en uno
`deploy_multus`, `sbi_tls` y `node_encryption`.

## 5. Primer despliegue: una sola red

En `node-master`, dentro de `kcd-porto-5g-zero-trust-lab/ansible`:

```bash
ansible-playbook site.yml -K
```

`-K` pide la contraseña de `sudo`. Tarda entre 15 y 30 minutos, casi todo en
descargas.

| Play | Qué hace | Si falla, mira |
|---|---|---|
| 1 | paquetes base, módulo SCTP, swap apagado | `apt`, internet |
| 1b | dn-gw (solo con Multus) | `systemctl status dn-gw-nat` en dn-gw |
| 2 | k3s server sin flannel ni kube-proxy | `sudo journalctl -u k3s -n 50` |
| 3 | k3s agent en los workers | `sudo journalctl -u k3s-agent -n 50` en el worker |
| 3b | rutas de CNI y plugins ipvlan/static (solo con Multus) | la salida de *Mostrar las rutas detectadas* |
| 4 | Helm, Cilium, Multus y NAD, Kyverno, metrics-server, Open5GS (UPF y plano de control), gNB y UE, `sbi-probe`, Tetragon y las políticas de Cilium | §14 |

Al final, `PLAY RECAP` con `failed=0` y un mensaje con el modo desplegado.

El playbook es idempotente. Si falla a mitad, corrige la causa y relanza el mismo
comando, o solo una parte con `--tags` (§15).

## 6. Comprobar que el core funciona

En `node-master` (el playbook deja el kubeconfig en `~/.kube/config`), desde la raíz
del repo.

**Nodos y Cilium**

```bash
kubectl get nodes -o wide          # los tres Ready, cada uno con su 192.168.100.x
cilium status                      # Cilium OK, Operator OK, Hubble Relay OK
```

**Pods**

```bash
kubectl -n 5g-cp get pods -o wide  # NF del core y MongoDB en node-worker1
kubectl -n 5g-up get pods -o wide  # open5gs-up-upf en node-worker2
kubectl -n 5g-ran get pods -o wide # gNB y UE en node-worker2
kubectl -n 5g-cp logs deploy/open5gs-cp-smf | grep -i pfcp   # asociación N4 con el UPF
```

**N2: el gNB se registra en el AMF**

```bash
kubectl -n 5g-ran logs deploy/ueransim-gnb | tail -n 20
#   NG Setup procedure is successful
```

**El UE se registra y abre una sesión PDU**

```bash
kubectl -n 5g-ran logs deploy/ueransim-ues | tail -n 30
#   Initial Registration is successful
#   PDU Session establishment is successful PSI[1]
#   TUN interface[uesimtun0, 10.45.0.2] is up.

UE=$(kubectl -n 5g-ran get pod -l app.kubernetes.io/name=ueransim-ue -o jsonpath='{.items[0].metadata.name}')
kubectl -n 5g-ran exec $UE -- ping -c 4 -I uesimtun0 8.8.8.8
kubectl -n 5g-ran exec $UE -- curl -s --interface uesimtun0 -o /dev/null -w "%{http_code}\n" https://example.com
```

**Prueba de humo y políticas**

```bash
make smoke            # attach=SI y una petición SBI legítima con respuesta 2xx
make policy-matrix    # sin clúster: flujos legítimos y de ataque en los dos modos
kubectl get cnp -A -l kcd.io/policy-set=lab
hubble observe -n 5g-cp --verdict DROPPED --last 20   # no debe haber drops entre NF legítimas
```

**Hubble UI desde el laptop**

```bash
cilium hubble ui --open-browser=false        # en node-master, puerto 12000
ssh -L 12000:localhost:12000 bryantxz10@192.168.100.10   # en el laptop
```

Y en el navegador, `http://localhost:12000`.

## 7. Endurecer el clúster y guardar un snapshot

`hardening.yml` aplica dos cosas que no son políticas de red: Pod Security Standards
por namespace y el taint del master, para que no corra carga del core.

```bash
ansible-playbook hardening.yml -K
```

El taint afecta a los pods que se programen a partir de ese momento: lo que ya
estaba en el master se queda donde está. En un despliegue nuevo, lanzarlo justo
después del primer `site.yml` es suficiente.

Apaga en orden (workers, master y, si está encendida, dn-gw) y toma un snapshot de
cada VM, por ejemplo `una-red-ok`:

```bash
for h in 192.168.100.11 192.168.100.12 192.168.100.13; do ssh bryantxz10@$h sudo poweroff; done
sudo poweroff
```

## 8. Redes dedicadas (Multus)

Antes de activarlas, comprueba con `helm template` que el chart de Gradiant acepta
las claves que usa el playbook: [`pruebas-fase1.md`](pruebas-fase1.md) §2. Es el paso
que más probabilidades tiene de fallar.

```bash
# en ansible/group_vars/all.yml
deploy_multus: true
```

```bash
ansible-playbook site.yml -K
```

Con esto entran en juego dn-gw, los plugins CNI, Multus, los NAD `access` y `n6`,
Kyverno con la política de admisión, multi-networkpolicy-iptables, el AMF, el UPF y
el gNB con sus interfaces dedicadas, y el overlay `multus` de Cilium. Al final, el
playbook comprueba que las interfaces existen dentro de los pods y que el gNB hace
NG Setup contra 10.10.0.10.

Comprobaciones y demos:

- [`pruebas-fase1.md`](pruebas-fase1.md): interfaces, NG Setup, PFCP, el UE saliendo
  por N6 y `tcpdump -ni n6` en dn-gw. Hubble ya no ve N2 ni N3.
- [`pruebas-fase2.md`](pruebas-fase2.md): un pod que pide la red `access` es
  rechazado por el API server (`kubectl apply -f
  attacks/attacker-access.yaml`), y las MultiNetworkPolicy.

Si algo falla, vuelve al snapshot `una-red-ok`. Poner `deploy_multus: false` y
relanzar no desinstala Multus ni Kyverno.

## 9. mTLS en la SBI

Primero comprueba el chart: [`pruebas-fase4.md`](pruebas-fase4.md) §2.

```bash
# en ansible/group_vars/all.yml
sbi_tls: true
```

```bash
ansible-playbook site.yml -K
make smoke              # sbi(mTLS)=200
make demo-l7-ciega      # la misma petición no autorizada al NRF
```

La CA y los certificados se generan en el master, en `/etc/kcd-lab/pki/sbi`, y no
salen de ahí salvo como Secrets del clúster. Para la demo hay que anotar qué
responde en cada caso: tabla de [`pruebas-fase4.md`](pruebas-fase4.md) §4.

## 10. Cifrado entre nodos (WireGuard)

```bash
# en ansible/group_vars/all.yml
node_encryption: true
```

```bash
ansible-playbook site.yml -K --tags cilium,policies
kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg encrypt status
```

Después, repite la prueba L7 del NRF para confirmar que sigue funcionando con
WireGuard: [`pruebas-fase3.md`](pruebas-fase3.md) §3.5.

## 11. Tetragon

Viene activado (`deploy_tetragon: true`). La demo:

```bash
make demo-tetragon
```

Una shell y un `curl` dentro del AMF mueren con código 137 antes de ejecutarse, y el
AMF sigue en marcha. Detalle, la observabilidad de sockets en las redes dedicadas y
los supuestos: [`pruebas-fase6.md`](pruebas-fase6.md).

Si el AMF no arranca con la política aplicada, bórrala
(`kubectl -n 5g-cp delete tracingpolicynamespaced amf-sin-shell`) y mira los eventos
de Tetragon: el entrypoint del chart puede estar lanzando algún binario de la lista.

## 12. Captura para el blast radius map

`tools/spec2policy` genera el blast radius map a partir de flujos reales de Hubble.
La captura se hace con la SBI en claro (`sbi_tls: false`): con mTLS no hay datos L7.
El procedimiento completo, con la visibilidad L7 necesaria y los comandos, está en
[`pruebas-fase5.md`](pruebas-fase5.md). La salida se copia en
[`blast-radius-map-plantilla.md`](blast-radius-map-plantilla.md) y su `.csv`.

## 13. Apagar y volver a encender

Apaga primero los workers y dn-gw, y luego el master. Al encender, primero el master,
después el resto. Espera dos o tres minutos y:

```bash
make status
```

MongoDB no guarda datos entre reinicios (volumen `emptyDir`). Si el UE no se
registra:

```bash
make subscribers      # vuelve a insertar el suscriptor
make ran-restart      # reinicia gNB y luego UE
```

## 14. Problemas frecuentes

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Ansible: `UNREACHABLE` | falta la llave SSH en esa VM | `ssh-copy-id bryantxz10@<IP>` |
| Ansible: `Missing sudo password` | falta `-K` | `ansible-playbook site.yml -K` |
| `Module sctp not found` | faltan los módulos extra del kernel | `sudo apt install -y linux-modules-extra-$(uname -r)` y relanzar |
| Nodos `NotReady` | Cilium aún no arranca en ese nodo | `kubectl -n kube-system get pods -l k8s-app=cilium -o wide` y sus logs |
| `helm --wait` de Open5GS se agota | imágenes descargando o bloqueadas | `kubectl -n 5g-cp get pods` y `describe pod` (sección *Events*) |
| `ImagePullBackOff` con `toomanyrequests` | límite de descargas anónimas de Docker Hub por IP pública | esperar y relanzar `--tags open5gs`, o configurar credenciales de Docker Hub en `/etc/rancher/k3s/registries.yaml` |
| `populate` en `Init:CrashLoopBackOff` al principio | MongoDB aún no estaba listo | se arregla solo en uno o dos minutos |
| gNB: *Esperando DNS del AMF* (una red) | no existe el Service `amf-n2` o el AMF no corre | `kubectl -n 5g-cp get endpoints amf-n2` |
| gNB: *NG Setup failure* tras reiniciar el AMF | el AMF cambió de IP (una red) | `make ran-restart` |
| UE: *Registration reject* o fallo de autenticación | falta el suscriptor en MongoDB | `make subscribers` y `make ran-restart` |
| `uesimtun0` existe pero no hay internet | NAT del UPF (una red) o dn-gw (Multus) | logs del UPF; en dn-gw, `ip route show 10.45.0.0/16` y `iptables -t nat -S DN-N6-NAT` |
| Pods del core con drops en Hubble tras aplicar las políticas | etiquetas distintas de las esperadas o una ruta del NRF que falta en la lista L7 | [`pruebas-fase3.md`](pruebas-fase3.md) §4 |
| Con Multus: la interfaz `n2`/`n3`/`access` no aparece en el pod | Cilium retiró la config de Multus, o rutas de CNI distintas | `ls <conf_dir>` en el worker; [`pruebas-fase1.md`](pruebas-fase1.md) §5 |
| Con Multus: pods legítimos rechazados por Kyverno | la política no reconoce al creador o las etiquetas | `kyverno_multus_guard_action: Audit`, `--tags admission` y `kubectl get policyreport -A` |
| Con TLS: NF que no pasan a Ready | sondas HTTP contra HTTPS, o el certificado no se montó | [`pruebas-fase4.md`](pruebas-fase4.md) §2 |
| El AMF muere al arrancar con Tetragon | la política mata algo del entrypoint | §11 |

Comandos que siempre ayudan:

```bash
make status
kubectl get events -A --sort-by=.lastTimestamp | tail -n 30
kubectl -n <ns> describe pod <pod>
kubectl -n <ns> logs <pod> --previous
```

## 15. Referencia: tags del playbook

| Tag | Qué repite |
|---|---|
| `prereqs` | paquetes, SCTP, swap |
| `k3s` | k3s server y agents |
| `cilium` | Cilium |
| `dn-gw` | router N6 |
| `multus` | rutas de CNI, plugins, Multus, NAD y patches del UPF y el gNB |
| `admission` | Kyverno y la política de redes dedicadas |
| `mnp` | multi-networkpolicy-iptables y las MultiNetworkPolicy |
| `open5gs` | UPF y plano de control |
| `tls` | PKI de la SBI, Secrets y `sbi-probe` |
| `ueransim` | gNB y UE |
| `tetragon` | Tetragon y sus políticas |
| `policies` | políticas de Cilium del modo elegido |

Ejemplo: `ansible-playbook site.yml -K --tags open5gs,ueransim`.

Todo el despliegue es con Ansible: `make up` es un atajo de
`ansible-playbook site.yml -K`.

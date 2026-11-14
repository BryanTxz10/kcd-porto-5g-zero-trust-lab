# Pruebas — Fase 1: redes dedicadas con Multus

Fase 1 del arco de la charla (**giro 1: lo que el CNI no ve**). N2 y N3 viajan por
la red `access` y la salida de los UE por `n6`, en interfaces ipvlan que Multus añade
a los pods, como en un operador. Ese tráfico **no pasa por el datapath de Cilium**:
ninguna CiliumNetworkPolicy lo filtra y Hubble no lo registra. Los controles de esas
redes son la Fase 2.

> **Estado de verificación.** Pasa `--syntax-check`, `ansible-lint` y yamllint, y
> las plantillas se han renderizado en local con las variables reales (NAD, values,
> patches, script de dn-gw). La extracción de las rutas de CNI se ha probado contra
> una config de containerd de ejemplo. **Nada de esta fase se ha ejecutado en un
> clúster.** Las claves del chart de Gradiant (§2) no se han comprobado contra el
> chart 2.3.4.

Topología, VMs y netplan: [`guia-vms-realista.md`](guia-vms-realista.md) (Fase 0).
Visión de conjunto: [`arquitectura.md`](arquitectura.md).

## 1. Qué hace el playbook con `deploy_multus: true`

| Pieza | Plan B (`false`) | Redes dedicadas (`true`) | Dónde |
|---|---|---|---|
| Rutas de CNI | por defecto | se leen de `bin_dir`/`conf_dir` en la config de containerd de k3s; todos los nodos deben coincidir | `site.yml`, play 3b |
| Plugins CNI | solo `cilium-cni` | + `ipvlan` y `static` (cni-plugins v1.4.1, sha256 verificado) | play 3b |
| Cilium | por defecto | `cni.exclusive=false` y las rutas de CNI de k3s | Helm de Cilium |
| Multus | no se instala | thick v4.0.2, con los `hostPath` ajustados a las rutas de k3s | `site.yml` |
| NAD | ninguno | `access` en 5g-cp, 5g-ran y 5g-up; `n6` en 5g-up. ipvlan L2, IPAM static con IP en la anotación | `templates/multus-nads.yaml.j2` |
| AMF | NGAP en `eth0` | `n2` = 10.10.0.10; NGAP ahí. `amf.yaml` completo en `customOpen5gsConfig`, SBI y métricas en `eth0` | `templates/open5gs-cp-multus-values.yaml.j2` |
| UPF | GTP-U en `eth0`, NAT propio | `n3` = 10.10.0.30 (`gtpu.dev: n3`, `advertise`), `n6` = 10.10.6.30, `enableNAT: false`; PFCP en `eth0` | `templates/open5gs-upf-multus-values.yaml.j2` |
| UPF, salida de los UE | `eth0` con MASQUERADE | initContainer (NET_ADMIN): `ip rule from 10.45.0.0/16 table 100`, `default via 10.10.6.1 dev n6 table 100` | `templates/upf-n6-route-patch.yaml.j2` |
| SMF | — | sin cambios: N4 por Cilium hacia el Service del UPF | — |
| gNB | N2/N3 en la IP del pod, AMF por Service headless | `access` = 10.10.0.20 para `ngapIp` y `gtpIp`, AMF en 10.10.0.10; `linkIp` (RLS) sigue en la red de pods; sin Service headless | `templates/ueransim-gnb-multus-patch.yaml.j2` |
| dn-gw | no se usa | `ip_forward`, ruta `10.45.0.0/16 via 10.10.6.30`, CGNAT y firewall de N6, iperf3 y HTTP en 10.10.6.1 | play `dn-gw` |

Las IP salen todas de `ansible/group_vars/all.yml`.

**Notas de diseño**

- **IP en la anotación, NAD por red.** El NAD es la red (`access`, `n6`), no la NF.
  Quién puede pedir cada red no lo decide el NAD sino la admisión (Kyverno, Fase 2):
  así un atacante que escriba `k8s.v1.cni.cncf.io/networks: access` es rechazado
  por el API server, que es la demo.
- **gNB por patch.** Añade la anotación y las variables `N2_IP`, `N3_IP` y
  `AMF_N2_ADDR`, que **no** existen en `bootstrap/manifests/ueransim.yaml`; un
  `kubectl apply` del base no deshace el patch. `ueransim-config/gnb.yaml` usa
  marcadores (`__N2_IP__`, `__N3_IP__`, `__AMF_N2__`) que sin el patch valen la IP
  del pod y el Service headless (plan B).
- **UPF por patch.** El policy routing va en un initContainer añadido con un patch
  estratégico idempotente tras el `helm upgrade`. Helm 3 lo conserva en upgrades
  posteriores (merge a tres vías) y el playbook lo vuelve a aplicar en cada
  ejecución. `rp_filter` no se toca: el netns del pod hereda el modo *loose* de
  Ubuntu, con el que las respuestas que entran por `n6` pasan.
- **dn-gw es la red de datos.** CGNAT y firewall de N6 viven fuera del core. Desde
  el pool de UE no se alcanzan redes privadas (10/8, 172.16/12, 192.168/16,
  100.64/10): un UE no puede usar N6 para entrar al clúster.

## 2. Antes de activar: comprobar el chart

Supuestos **no verificados** contra `oci://registry-1.docker.io/gradiantcharts/open5gs`
2.3.4:

| Supuesto | Dónde se usa |
|---|---|
| `amf.podAnnotations` y `upf.podAnnotations` llegan al pod (`smf.podAnnotations` ya se usa en `open5gs-values.yaml`) | anotación de Multus |
| `amf.customOpen5gsConfig` reemplaza el `amf.yaml` entero | NGAP en 10.10.0.10 |
| El `amf.yaml` de la plantilla no pierde nada de lo que pone el chart (URI del SCP, métricas, `amf_name`…) | AMF completo |
| `upf.config.upf.gtpu.dev` y `.advertise` existen | GTP-U en `n3`, anuncio de 10.10.0.30 |
| `enableNAT: false` quita el MASQUERADE del UPF | CGNAT solo en dn-gw |
| El Deployment del UPF se llama `open5gs-up-upf` | patch del initContainer |

En el master, con los ficheros que deja el playbook en `/tmp/cib46/` (o generándolos
con `--tags open5gs,multus`):

```bash
# 1) amf.yaml que genera el chart SIN el fichero de Multus (referencia)
helm template open5gs-cp oci://registry-1.docker.io/gradiantcharts/open5gs --version 2.3.4 \
  -n 5g-cp -f /tmp/cib46/open5gs-values.yaml \
  | yq 'select(.kind=="ConfigMap" and .metadata.name=="open5gs-cp-amf")' > /tmp/amf-chart.yaml

# 2) el mismo CON el fichero de Multus
helm template open5gs-cp oci://registry-1.docker.io/gradiantcharts/open5gs --version 2.3.4 \
  -n 5g-cp -f /tmp/cib46/open5gs-values.yaml -f /tmp/cib46/open5gs-cp-multus-values.yaml \
  | yq 'select(.kind=="ConfigMap" and .metadata.name=="open5gs-cp-amf")' > /tmp/amf-multus.yaml

diff /tmp/amf-chart.yaml /tmp/amf-multus.yaml   # solo debe cambiar ngap (y nada que falte)

# 3) UPF: anotación, gtpu y NAT
helm template open5gs-up oci://registry-1.docker.io/gradiantcharts/open5gs --version 2.3.4 \
  -n 5g-up -f /tmp/cib46/open5gs-upf-values.yaml -f /tmp/cib46/open5gs-upf-multus-values.yaml \
  | grep -nE 'cni.cncf.io/networks|gtpu|dev: n3|advertise|10\.10\.0\.30|enableNAT|MASQUERADE|name: open5gs-up-upf$'
```

Si una clave no existe o no hace lo esperado, el ajuste está en las plantillas
`ansible/templates/open5gs-*-multus-values.yaml.j2`. Los nombres de los ConfigMaps
de arriba también son un supuesto: lista los de `helm template` si no aparecen.

## 3. Orden

1. **Plan B primero.** Con `deploy_multus: false`, `ansible-playbook site.yml -K` y
   comprueba que el UE se registra y tiene `uesimtun0`. Snapshot de las VMs.
2. Comprueba el chart (§2).
3. `deploy_multus: true` y `ansible-playbook site.yml -K`. El play `dn-gw`, el play
   3b y las tareas `[multus]` dejan de saltarse. Al final el playbook comprueba las
   interfaces dentro de los pods y que el gNB hace NG Setup.
4. Si falla: vuelve al snapshot. Volver a `false` y relanzar **no** desinstala
   Multus, los NAD ni el initContainer del UPF.

## 4. Qué comprobar y qué debe verse (no ejecutado aún)

En el master:

```bash
# rutas de CNI y Multus
ansible-playbook site.yml -K --tags multus | grep -A1 'Mostrar las rutas'
kubectl -n kube-system get ds kube-multus-ds
kubectl get network-attachment-definitions -A        # access ×3, n6 ×1

# interfaces dentro de los pods (si la imagen no trae 'ip', usar /sys/class/net)
kubectl -n 5g-cp  exec deploy/open5gs-cp-amf -- ip -br a      # n2  10.10.0.10/24
kubectl -n 5g-up  exec deploy/open5gs-up-upf -- ip -br a      # n3  10.10.0.30/24, n6 10.10.6.30/24
kubectl -n 5g-ran exec deploy/ueransim-gnb   -- ip -br a      # access 10.10.0.20/24

# NG Setup contra 10.10.0.10
kubectl -n 5g-ran logs deploy/ueransim-gnb | grep -E 'AMF en|NG Setup'
#   gNB: radio 10.42.x.x, N2 10.10.0.20, N3 10.10.0.20; AMF en 10.10.0.10
#   NG Setup procedure is successful

# PFCP SMF→UPF y anuncio de N3 en 10.10.0.30
kubectl -n 5g-cp logs deploy/open5gs-cp-smf | grep -iE 'pfcp|associated'
kubectl -n 5g-up logs deploy/open5gs-up-upf | grep -iE 'gtpu|10\.10\.0\.30|associated'

# policy routing del UPF
kubectl -n 5g-up logs deploy/open5gs-up-upf -c n6-route
#   1000: from 10.45.0.0/16 lookup 100
#   default via 10.10.6.1 dev n6

# el UE sale por N6
kubectl -n 5g-ran exec deploy/ueransim-ues -- ping -c3 -I uesimtun0 8.8.8.8
kubectl -n 5g-ran exec deploy/ueransim-ues -- curl -s --interface uesimtun0 http://10.10.6.1:8080/
```

En **dn-gw**:

```bash
ip route show 10.45.0.0/16                         # 10.45.0.0/16 via 10.10.6.30 dev n6
sudo iptables -t nat -S DN-N6-NAT                  # MASQUERADE de 10.45.0.0/16 por ens33
sudo iptables -L DN-N6-FWD -v -n                   # contadores del firewall de N6
sudo tcpdump -ni n6 icmp                           # durante el ping: 10.45.x.x > 8.8.8.8
systemctl status dn-iperf3 dn-http
```

La prueba que importa para la charla, **Hubble ya no ve N2 ni N3**:

```bash
hubble observe --protocol sctp --last 50     # plan B: NGAP gNB→AMF; redes dedicadas: nada
hubble observe --port 2152 --last 50         # plan B: GTP-U gNB↔UPF; redes dedicadas: nada
```

## 5. Otros supuestos sin verificar

- **Rutas de CNI de k3s.** Se espera que con `--flannel-backend=none` k3s use
  `/opt/cni/bin` y `/etc/cni/net.d`. El playbook lo lee en vez de suponerlo; en un
  worker, `ls <conf_dir>` debe mostrar `00-multus.conf` antes que la conflist de
  Cilium.
- **`cni.exclusive=false` en Cilium 1.15.4.** Si Cilium sigue renombrando la config
  de Multus (`*.cilium_bak`), la segunda interfaz no aparece.
- **ipvlan L2 en el mismo worker.** gNB y UPF comparten la NIC padre `access` en
  worker2; los esclavos ipvlan de un mismo padre se ven entre sí, pero el host no ve
  a sus pods por esa NIC (esperado).
- **Camino bash.** `make up` con `DEPLOY_MULTUS=1` sigue siendo el Multus macvlan del
  lab v2. Las redes dedicadas solo existen en Ansible.

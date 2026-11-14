# Fase 1 — Tres redes con Multus (ipvlan) y dn-gw

Fase 1 del arco de la charla (**giro 1: lo que el CNI no ve**). N2 y N3 viajan por
la red `access` y la salida de los UE por `n6`, en interfaces que Multus añade a los
pods. Ese tráfico **no pasa por el datapath de Cilium**: ninguna
CiliumNetworkPolicy lo ve ni lo filtra, y Hubble tampoco lo registra.

> **Estado de verificación.** Todo lo de esta fase pasa `--syntax-check`,
> `ansible-lint` y yamllint, y las plantillas se han renderizado en local con las
> variables reales. **No se ha ejecutado contra un clúster.** Las claves del chart
> de Gradiant que usa (§4) no se han comprobado contra el chart 2.3.4. Lo no
> verificado está marcado como tal.

Topología, VMs y netplan: [`guia-vms-realista.md`](guia-vms-realista.md) (Fase 0).

## 1. Qué cambia con `deploy_multus: true`

| Pieza | Plan B (`false`) | Fase 1 (`true`) | Dónde |
|---|---|---|---|
| Plugins CNI | solo `cilium-cni` | + `ipvlan` y `static` (cni-plugins v1.4.1, sha256 verificado) | `site.yml`, play 1 |
| Cilium | por defecto | `cni.exclusive=false` (si no, retira la config de Multus) | `site.yml`, Helm de Cilium |
| Multus | no se instala | thick daemonset v4.0.2 | `site.yml` |
| NAD | ninguno | `amf-n2`, `gnb-access`, `upf-n3`, `upf-n6`: ipvlan L2, IP fija dentro del NAD | `templates/multus-nads.yaml.j2` |
| AMF | NGAP en la IP del pod | interfaz `n2` = 10.10.0.10, NGAP en esa IP | `templates/open5gs-cp-multus-values.yaml.j2` |
| UPF | GTP-U en la IP del pod, NAT propio | `n3` = 10.10.0.30 (GTP-U), `n6` = 10.10.6.30, **sin NAT** | `templates/open5gs-upf-multus-values.yaml.j2` |
| UPF, salida de los UE | por `eth0` (Cilium) con MASQUERADE | policy routing: `from 10.45.0.0/16 → table 106 → default via 10.10.6.1 dev n6` | `templates/upf-n6-route-patch.yaml.j2` |
| gNB | N2/N3 en la IP del pod, AMF por Service headless | interfaz `access` = 10.10.0.20 para N2 y N3, AMF por 10.10.0.10 | `templates/ueransim-gnb-multus-patch.yaml.j2` |
| dn-gw | no se usa | `ip_forward`, ruta `10.45.0.0/16 via 10.10.6.30`, MASQUERADE por mgmt | play `dn-gw` de `site.yml` |

Las IP salen todas de `ansible/group_vars/all.yml` (`multus_nads`, `amf_n2_ip`,
`upf_n6_ip`, `dn_gw_n6_ip`, `ue_pool_cidr`…). Nada lleva IP escrita a mano fuera de
ahí.

Lo que **sigue** por la red de pods (y por tanto bajo Cilium): SBI, N4 (PFCP
SMF→UPF), DNS y la radio simulada (RLS UE↔gNB).

### Por qué un NAD por interfaz y no uno compartido con IP en la anotación

Con la IP dentro del NAD, cada objeto es auditable por sí solo (`upf-n6` *es*
10.10.6.30 sobre `n6`) y un pod que no debería estar en la red no puede pedir una IP
en ella con solo escribir una anotación. Coste: un NAD por réplica, que en este lab
es una.

### Por qué un patch para el gNB y el UPF

- **gNB** (manifiesto propio): el patch añade la anotación de Multus y las variables
  `N2_IP`, `N3_IP` y `AMF_N2_ADDR`, que **no** existen en
  `bootstrap/manifests/ueransim.yaml`. Así un `kubectl apply` del manifiesto base no
  deshace el patch, y sin el patch el gNB se comporta como en el lab v2
  (`ueransim-config/gnb.yaml` usa marcadores `__N2_IP__`, `__N3_IP__`, `__AMF_N2__`
  con la IP del pod y el Service headless por defecto).
- **UPF** (chart de Gradiant): no sabemos si el chart admite `initContainers` propios,
  así que el policy routing se añade con un patch estratégico idempotente después del
  `helm upgrade`. Helm 3 conserva el campo en upgrades posteriores (merge a tres vías)
  y el playbook lo vuelve a comprobar en cada ejecución. El initContainer es
  privilegiado porque escribe sysctl de red del netns del pod; `5g-up` ya está en
  `enforce=privileged` (`hardening.yml`).

## 2. Orden recomendado

1. **Primero el plan B.** Con `deploy_multus: false`, despliega y comprueba que el
   UE se registra y tiene `uesimtun0` (sección de verificación de
   `guia-lab-desde-cero.md`). Así cualquier fallo posterior es de la Fase 1, no del
   core. Snapshot de las VMs.
2. **Comprueba el chart** (§4) en el master antes de activar nada.
3. Pon `deploy_multus: true` y lanza:

   ```bash
   cd ansible && ansible-playbook site.yml -K
   ```

   El play `dn-gw` y todas las tareas `[multus]` dejan de saltarse. El UPF y el gNB
   se reinician una vez por el patch.
4. Si algo falla: `deploy_multus: false`, vuelve a lanzar el playbook (o vuelve al
   snapshot). Ojo: volver a `false` **no** desinstala Multus, ni los NAD, ni el
   initContainer del UPF; el snapshot es lo más limpio.

## 3. Cómo comprobar que funciona (no verificado aún)

Ejecutar en el master salvo que se diga otra cosa.

```bash
# Multus y NAD
kubectl -n kube-system get ds kube-multus-ds
kubectl get network-attachment-definitions -A

# Interfaces dentro de los pods (deben existir con su IP)
kubectl -n 5g-cp  exec deploy/open5gs-cp-amf -- ip -br a show n2
kubectl -n 5g-up  exec deploy/open5gs-up-upf -- ip -br a
kubectl -n 5g-ran exec deploy/ueransim-gnb   -- ip -br a show access

# N2 por la red access: el gNB debe decir "NG Setup procedure is successful"
kubectl -n 5g-ran logs deploy/ueransim-gnb | grep -E 'N2|NG Setup|AMF en'

# Policy routing del UPF y sesión PDU
kubectl -n 5g-up exec deploy/open5gs-up-upf -- ip rule show
kubectl -n 5g-up exec deploy/open5gs-up-upf -- ip route show table 106
kubectl -n 5g-ran exec deploy/ueransim-ues -- ping -c3 -I uesimtun0 1.1.1.1
```

En **dn-gw**:

```bash
ip route show 10.45.0.0/16                  # via 10.10.6.30 dev n6
sudo iptables -t nat -S POSTROUTING | grep 10.45.0.0/16
sudo tcpdump -ni n6 icmp                    # durante el ping del UE: origen 10.45.x.x
```

Y la prueba que importa para la charla: **Hubble no ve N2 ni N3.**

```bash
hubble observe --protocol sctp --last 50    # plan B: NGAP gNB→AMF; Fase 1: nada
hubble observe --port 2152 --last 50        # plan B: GTP-U gNB↔UPF; Fase 1: nada
```

## 4. Lo que hay que comprobar en el chart antes de activar

Las claves siguientes **no se han verificado** contra el chart
`oci://registry-1.docker.io/gradiantcharts/open5gs` 2.3.4 (no había acceso al
registro ni a Artifact Hub desde donde se escribió esta fase):

| Supuesto | Dónde se usa |
|---|---|
| `amf.podAnnotations` y `upf.podAnnotations` llegan al pod (el SMF ya usa `smf.podAnnotations` en `open5gs-values.yaml`) | anotación `k8s.v1.cni.cncf.io/networks` |
| `amf.customOpen5gsConfig` / `upf.customOpen5gsConfig` se fusionan sobre el `amf.yaml`/`upf.yaml` que genera el chart, y una lista (`ngap.server`, `gtpu.server`) **sustituye** a la del chart | NGAP en 10.10.0.10, GTP-U en 10.10.0.30 |
| El Deployment del UPF se llama `open5gs-up-upf` | patch del initContainer |
| `upf.config.subnetList[].enableNAT: false` quita el MASQUERADE del UPF | NAT solo en dn-gw |

Comprobación en el master, sin desplegar (con los ficheros que deja el playbook en
`/tmp/cib46/`, o generándolos con `--tags open5gs` y `deploy_multus: true`):

```bash
helm template open5gs-cp oci://registry-1.docker.io/gradiantcharts/open5gs --version 2.3.4 \
  -n 5g-cp -f /tmp/cib46/open5gs-values.yaml -f /tmp/cib46/open5gs-cp-multus-values.yaml \
  | grep -nE 'k8s.v1.cni.cncf.io/networks|ngap:|10\.10\.0\.10' 
helm template open5gs-up oci://registry-1.docker.io/gradiantcharts/open5gs --version 2.3.4 \
  -n 5g-up -f /tmp/cib46/open5gs-upf-values.yaml -f /tmp/cib46/open5gs-upf-multus-values.yaml \
  | grep -nE 'k8s.v1.cni.cncf.io/networks|gtpu:|10\.10\.0\.30|MASQUERADE|kind: Deployment' -A1
```

Si `customOpen5gsConfig` no existe con ese nombre o no sustituye las listas, el
ajuste está en las dos plantillas `templates/open5gs-*-multus-values.yaml.j2`.

## 5. Otros supuestos sin verificar

- **Rutas CNI de k3s.** Con `--flannel-backend=none`, k3s usa `/etc/cni/net.d` y
  `/opt/cni/bin`, que es donde escriben Cilium y Multus thick por defecto. Si en tu
  versión no fuese así, Multus no se encadena; comprueba
  `ls /etc/cni/net.d` en un worker (debe aparecer `00-multus.conf` antes que
  `05-cilium.conflist`).
- **ipvlan L2 entre pods del mismo worker.** gNB y UPF comparten la NIC padre
  `access` en worker2; en ipvlan L2 los esclavos de un mismo padre se ven entre sí,
  pero el **host** no ve a sus pods por esa NIC (esperado, no hace falta).
- **rp_filter.** El initContainer pone `rp_filter=0` en el pod del UPF porque las
  respuestas de internet entran por `n6` y la ruta principal hacia su origen es
  `eth0`; con filtrado estricto se descartarían.
- **Camino bash.** `make up` / `DEPLOY_MULTUS=1` sigue siendo el Multus macvlan del
  lab v2. La arquitectura de tres redes solo está en Ansible.

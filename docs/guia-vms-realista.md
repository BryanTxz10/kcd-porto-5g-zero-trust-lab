# Guía realista de VMs: cuatro nodos y tres redes en VMware Workstation (Fase 0)

> **Qué cubre:** crear las VMs y dejar el sistema operativo listo para que
> **Ansible** haga todo lo demás. Aquí no se despliega nada de Kubernetes ni
> del core 5G: eso sale de `ansible/site.yml` en las fases siguientes.
>
> **Para quién:** Bryan, reinstalando el lab desde cero para la charla de KCD
> Porto. Pensado para hacerlo copiando y pegando, en orden.
>
> **Hipervisor:** VMware Workstation Pro 17 en el laptop. **SO:** Ubuntu Server
> 22.04.5 LTS (amd64). **Usuario en todas las VMs:** `bryantxz10`.
>
> **Estado de verificación:** esta guía se escribió sin clúster disponible (el
> lab anterior está destruido). Los pasos de VMware y netplan siguen la
> documentación de ambos y la experiencia del lab v2
> (`docs/guia-lab-desde-cero.md`), pero **no se han vuelto a ejecutar**. Las
> cosas marcadas con ⚠️ son las que conviene comprobar con más calma.

---

## Índice

0. [Qué vas a construir](#0-qué-vas-a-construir)
1. [Antes de empezar](#1-antes-de-empezar)
2. [Crear los LAN segments ACCESS y N6](#2-crear-los-lan-segments-access-y-n6)
3. [Crear la VM plantilla e instalar Ubuntu](#3-crear-la-vm-plantilla-e-instalar-ubuntu)
4. [Configuración base y snapshot](#4-configuración-base-y-snapshot)
5. [Clonar los nodos y crear dn-gw](#5-clonar-los-nodos-y-crear-dn-gw)
6. [Agregar las NIC según la tabla](#6-agregar-las-nic-según-la-tabla)
7. [Personalizar cada clon](#7-personalizar-cada-clon)
8. [Obtener las MAC de cada NIC](#8-obtener-las-mac-de-cada-nic)
9. [Netplan: renombrar por MAC y asignar IP](#9-netplan-renombrar-por-mac-y-asignar-ip)
10. [Verificación](#10-verificación)
11. [Plan B: `deploy_multus: false`](#11-plan-b-deploy_multus-false)
12. [Inventario de Ansible](#12-inventario-de-ansible)
13. [Snapshot y qué sigue](#13-snapshot-y-qué-sigue)
14. [Problemas frecuentes](#14-problemas-frecuentes)

---

## 0. Qué vas a construir

Cuatro VMs y tres redes, agrupadas por **zona de confianza**: lo que viene de
la radio (access), lo interno del core (mgmt) y lo que sale a internet (n6).

```
   Tu laptop con VMware Workstation
   mgmt = VMnet8 (NAT) 192.168.100.0/24 · gateway y DNS .2 · laptop .1
   ──────────┬─────────────────┬─────────────────┬─────────────────┬────────
             │.10              │.11              │.12              │.13
      ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐
      │ node-master  │  │ node-worker1 │  │ node-worker2 │  │    dn-gw     │
      │ k3s server   │  │ sitio central│  │ sitio borde  │  │ router N6    │
      │ (con taint)  │  │ CP 5G, Mongo │  │ UPF gNB UE   │  │ CGNAT        │
      │ solo mgmt    │  │ mgmt, access │  │ mgmt acc. n6 │  │ mgmt, n6     │
      └──────────────┘  └──────┬───────┘  └──┬───────┬───┘  └──────┬───────┘
                               │access       │access │n6           │n6
   ACCESS 10.10.0.0/24         │             │       │             │
   ────────────────────────────┴─────────────┘       │             │
   N6 10.10.6.0/24                                   └─────────────┘

   ACCESS y N6 son LAN segments de VMware: L2 aislados, sin DHCP, sin
   adaptador en el host. En los workers access/n6 no llevan IP (padre de
   ipvlan); en dn-gw n6 = 10.10.6.1/24.
```

**Nodos**

| VM | Rol (equivalente en un operador) | vCPU | RAM | NIC |
|---|---|---|---|---|
| `node-master` (.10) | Control de Kubernetes, con taint (no corre carga 5G) | 2 | 4 GB | mgmt |
| `node-worker1` (.11) | Sitio central: plano de control 5G y MongoDB | 2 | 4,5 GB | mgmt, access |
| `node-worker2` (.12) | Sitio de borde: UPF, gNB, UE y atacantes (como DISH, que pone UPF y CU en la Local Zone) | 2 | 4,5 GB | mgmt, access, n6 |
| `dn-gw` (.13) | Red de datos: router N6 con CGNAT hacia internet | 1 | 1 GB | mgmt, n6 |

Unos **14 GB de RAM** en total. Si el laptop no da, baja los dos workers a
4 GB (12 GB en total).

**Redes**

| Red | En VMware | Subred | Qué viaja | Quién la ve |
|---|---|---|---|---|
| mgmt / clúster | **VMnet8 (NAT)** | 192.168.100.0/24; pods 10.42.0.0/16 (VXLAN); Services 10.43.0.0/16 | Kubernetes, SBI (HTTP/2), N4 (PFCP), DNS, RLS UE-gNB | Cilium y Hubble |
| access | **LAN segment `ACCESS`** | 10.10.0.0/24 | N2 (NGAP/SCTP) y N3 (GTP-U) | Multus (ipvlan L2) |
| n6 | **LAN segment `N6`** | 10.10.6.0/24 | Tráfico de los UE hacia la red de datos | Multus y dn-gw |

- N2 y N3 comparten la red de acceso, como en muchos operadores; ellos además
  las separan con VLAN. Aquí eso **se declara, no se implementa**.
- Los LAN segments de VMware son **L2 aislados**: sin DHCP, sin NAT, sin
  adaptador en el host. Ni tu laptop ni las otras redes los ven.
- En los **workers**, las NIC `access` y `n6` **no llevan IP**: son solo el
  padre de las interfaces ipvlan que Multus da a los pods. Las IP las tienen
  los pods.
- En **dn-gw**, `n6` lleva **10.10.6.1/24**.

**IP fijas** (están en `ansible/group_vars/all.yml`):

| Quién | Red | IP |
|---|---|---|
| AMF (N2) | access | 10.10.0.10 |
| gNB (N2 y N3) | access | 10.10.0.20 |
| UPF (N3) | access | 10.10.0.30 |
| UPF (N6) | n6 | 10.10.6.30 |
| dn-gw | n6 | 10.10.6.1 |
| Pool de UE | (sesiones PDU) | 10.45.0.0/16 |

dn-gw tendrá la ruta `10.45.0.0/16 via 10.10.6.30` y hará MASQUERADE por mgmt
hacia internet. **Eso lo configura Ansible en la Fase 1**, no esta guía.

> **Por qué ipvlan y no macvlan.** macvlan inventa una MAC por pod y la vNIC
> de VMware tendría que aceptar tramas para MACs que no son la suya (modo
> promiscuo), que en Workstation es frágil. ipvlan L2 comparte la MAC de la NIC
> padre: el switch virtual solo ve una MAC por VM y no hay que tocar nada.

---

## 1. Antes de empezar

**Laptop**

- CPU x86_64 con virtualización activada (VT-x / AMD-V). Las imágenes de
  UERANSIM son solo amd64.
- RAM: **16 GB** recomendados para los 14 GB de VMs. Con menos, workers a 4 GB.
- Disco libre: **~130 GB** (los discos crecen según se usan; dn-gw usa muy
  poco).

**Descargas**

1. **VMware Workstation Pro 17** (gratis para uso personal, portal de Broadcom).
2. **Ubuntu Server 22.04.5 LTS** (amd64): `https://releases.ubuntu.com/22.04/`
   → `ubuntu-22.04.5-live-server-amd64.iso`. No la cambies por 24.04: es la
   versión de referencia de Open5GS 2.7.5 y del lab anterior.

**Red NAT fijada**

La red mgmt es la **VMnet8 (NAT)** fijada a `192.168.100.0/24`, con gateway y
DNS en `192.168.100.2` y DHCP solo en `.128-.254`. Si no lo hiciste ya, sigue
la sección 2.1 de `docs/guia-lab-desde-cero.md` (Edit → Virtual Network
Editor). Comprueba en PowerShell con `ipconfig` que *VMware Network Adapter
VMnet8* tiene la IP `192.168.100.1`.

---

## 2. Crear los LAN segments ACCESS y N6

Un LAN segment es un switch virtual privado entre VMs. Se crean desde la
configuración de cualquier VM y después quedan disponibles para todas.

1. Con cualquier VM seleccionada (puede ser la plantilla de la sección 3, una
   vez creada): **VM → Settings… → pestaña Hardware → Network Adapter**.
2. En *Network connection*, marca **LAN segment** y pulsa el botón
   **LAN Segments…**.
3. Pulsa **Add** y escribe `ACCESS`. Pulsa **Add** otra vez y escribe `N6`.
   **OK**.
4. **Importante:** vuelve a dejar ese adaptador en **NAT** antes de cerrar
   (acabas de usar el diálogo solo para crear la lista). **OK**.

Qué NO tiene un LAN segment: DHCP, puerta de enlace, salida a internet,
adaptador en el host. Todo eso es intencional: así nadie llega a N2/N3 ni a N6
salvo quien tiene una pata en esa red.

---

## 3. Crear la VM plantilla e instalar Ubuntu

Creamos **una** VM con solo la NIC mgmt, la dejamos lista y la clonamos tres
veces (sección 5). Las NIC extra se añaden **después** de clonar (sección 6):
así el instalador nunca ve `access` ni `n6` y no intenta ponerles DHCP.

### 3.1 Crear la VM en VMware

1. **File → New Virtual Machine…** → **Typical** → **Next**.
2. **I will install the operating system later** → **Next**. (No uses el ISO
   aquí: activaría el *Easy Install*, que instala sin preguntar la red ni el
   usuario.)
3. **Guest OS:** *Linux* · **Version:** *Ubuntu 64-bit* → **Next**.
4. **Name:** `node-master` → **Next**.
5. **Maximum disk size:** `40` GB · *Split virtual disk into multiple files*
   → **Next**.
6. **Customize Hardware…**:
   - **Memory:** `4096` MB.
   - **Processors:** 1 procesador × 2 núcleos.
   - **New CD/DVD:** *Use ISO image file* → el ISO de 22.04.5 · *Connect at
     power on*.
   - **Network Adapter:** **NAT** · *Connect at power on*. (Esta será `mgmt`.)
   - Quita **Sound Card** y **Printer**.
   - **Close** → **Finish**.

### 3.2 Instalar Ubuntu Server 22.04.5

Enciende la VM. Clic dentro de la ventana para capturar el teclado
(`Ctrl+Alt` para soltarlo).

1. **Try or Install Ubuntu Server**.
2. **Language:** *English* (los errores se buscan mejor en inglés).
3. *Installer update available* → **Continue without updating**.
4. **Keyboard:** el tuyo → **Done**.
5. **Type of install:** *Ubuntu Server* (no *minimized*) → **Done**.
6. **Network connections:** verás una sola interfaz, normalmente `ens33`, con
   DHCP. Entra en ella → **Edit IPv4**:
   - **IPv4 Method:** *Manual*
   - **Subnet:** `192.168.100.0/24`
   - **Address:** `192.168.100.10`
   - **Gateway:** `192.168.100.2`
   - **Name servers:** `192.168.100.2,1.1.1.1`
   - **Save** → **Done**.
7. **Proxy:** vacío → **Done**.
8. **Mirror:** el propuesto; espera a que pase el test → **Done**.
9. **Storage:** *Use an entire disk* y **desmarca** *Set up this disk as an
   LVM group* (con LVM solo usa la mitad del disco para `/`). **Done** →
   **Done** → **Continue**.
10. **Profile setup:**
    - *Your name:* `Bryan`
    - *Your server's name:* `node-master`
    - *Pick a username:* **`bryantxz10`**
    - *Password:* la que quieras (será la de `sudo`). → **Done**.
11. **Ubuntu Pro:** *Skip for now* → **Continue**.
12. **SSH Setup:** marca **Install OpenSSH server** → **Done**.
13. **Snaps:** nada → **Done**.
14. *Installation complete!* → **Reboot Now**. Si pide quitar el medio, Enter.

Entra en la consola con `bryantxz10`.

---

## 4. Configuración base y snapshot

Todo esto se hace **una vez** en la plantilla; los clones lo heredan.

```bash
# Red
ip -br a                          # ens33 UP con 192.168.100.10/24
ping -c 3 192.168.100.2           # gateway de VMware
ping -c 3 github.com              # DNS + internet

# Paquetes
sudo apt update && sudo apt -y full-upgrade
sudo apt install -y curl git make vim htop jq open-vm-tools
sudo timedatectl set-timezone Europe/Paris

# Swap apagado (Kubernetes); Ansible también lo hace, pero así ya está
sudo swapoff -a
sudo sed -i '/\sswap\s/ s/^#*/#/' /etc/fstab

# Módulo SCTP (N2/NGAP). Si dice "not found":
#   sudo apt install -y linux-modules-extra-$(uname -r)
sudo modprobe sctp
echo sctp | sudo tee /etc/modules-load.d/sctp.conf

# Nombres de las cuatro VMs (red mgmt)
cat <<'EOF' | sudo tee -a /etc/hosts
192.168.100.10 node-master
192.168.100.11 node-worker1
192.168.100.12 node-worker2
192.168.100.13 dn-gw
EOF

# Firewall apagado (debe decir "Status: inactive")
sudo ufw status

sudo poweroff
```

En VMware, con la VM apagada: **VM → Snapshot → Take Snapshot…** → nombre
`base-limpia`.

---

## 5. Clonar los nodos y crear dn-gw

Con `node-master` apagada, tres veces **VM → Manage → Clone…**:

1. **Clone from:** *An existing snapshot* → `base-limpia` → **Next**.
2. **Clone type:** **Create a full clone** → **Next**.
3. **Name:** `node-worker1` / `node-worker2` / `dn-gw` → **Finish** → **Close**.

dn-gw se crea igual que los workers (es un clon de la misma plantilla); lo que
cambia es el hardware. Ajusta los recursos de cada clon en **VM → Settings…**
(VM apagada):

| VM | Memory | Processors |
|---|---|---|
| `node-worker1` | `4608` MB (4,5 GB) — o `4096` si el laptop no da | 1 × 2 |
| `node-worker2` | `4608` MB (4,5 GB) — o `4096` si el laptop no da | 1 × 2 |
| `dn-gw` | `1024` MB | 1 × 1 |

El disco de dn-gw sigue siendo de 40 GB "máximos", pero solo ocupa lo que
usa (unos pocos GB). No hace falta reducirlo.

VMware genera una MAC nueva para la NIC mgmt de cada clon. Si al encender
alguna VM pregunta *moved it / copied it*, responde **I copied it**.

---

## 6. Agregar las NIC según la tabla

Con cada VM **apagada**, en **VM → Settings… → Hardware → Add… → Network
Adapter → Finish**, y luego selecciona el adaptador nuevo y marca
**LAN segment** con el segmento que toque:

| VM | Network Adapter (existente) | Network Adapter 2 | Network Adapter 3 |
|---|---|---|---|
| `node-master` | NAT (mgmt) | — | — |
| `node-worker1` | NAT (mgmt) | LAN segment **ACCESS** | — |
| `node-worker2` | NAT (mgmt) | LAN segment **ACCESS** | LAN segment **N6** |
| `dn-gw` | NAT (mgmt) | LAN segment **N6** | — |

Deja marcado *Connect at power on* en todos. No toques el adaptador NAT.

> **La trampa.** Dentro de Ubuntu la primera NIC suele llamarse `ens33`, pero
> las siguientes salen como `ens34`, `ens37`, `ens38`… según el slot PCI que
> VMware les asigne, y ese nombre **puede cambiar** si quitas o añades
> hardware, o entre un clon y otro. VMware **no garantiza nombres estables**.
> Por eso en la sección 9 las renombramos por **MAC**, que sí es estable
> mientras no la regeneres.

---

## 7. Personalizar cada clon

Los clones arrancan con el hostname y la IP de la plantilla (`.10`). Hazlo
con **`node-master` apagada y un solo clon encendido a la vez**.

Enciende el clon, entra por la consola con `bryantxz10` y ejecuta, cambiando
las dos primeras líneas:

```bash
NEW_NAME=node-worker1        # node-worker2 | dn-gw
NEW_IP=192.168.100.11        # .12          | .13

# 1) Hostname (k3s usa el hostname como nombre del nodo)
sudo hostnamectl set-hostname "$NEW_NAME"
sudo sed -i "s/^127\.0\.1\.1.*/127.0.1.1 $NEW_NAME/" /etc/hosts

# 2) IP de mgmt en el netplan que dejó el instalador
sudo sed -i "s#192.168.100.10/24#$NEW_IP/24#" /etc/netplan/00-installer-config.yaml
grep -n "/24" /etc/netplan/00-installer-config.yaml      # debe mostrar la IP nueva

# 3) machine-id único (los clones lo heredan igual)
sudo rm -f /etc/machine-id /var/lib/dbus/machine-id
sudo systemd-machine-id-setup

# 4) Llaves SSH del servidor nuevas (si no, las 4 VMs tienen la misma)
sudo rm -f /etc/ssh/ssh_host_*
sudo dpkg-reconfigure openssh-server

sudo reboot
```

Al volver, comprueba `hostname`, `ip -br a` (la IP nueva en `ens33`) y
`ping -c 2 192.168.100.2`. Apaga y repite con el siguiente clon.

Si el archivo de netplan no se llama `00-installer-config.yaml`, mira
`ls /etc/netplan/` y usa el que haya.

---

## 8. Obtener las MAC de cada NIC

Necesitas saber, por cada VM, **qué MAC está conectada a qué red**. Dos
fuentes que deben coincidir:

**A) En VMware (quién está en qué red).** VM apagada → **VM → Settings… →
Hardware** → selecciona cada *Network Adapter* → **Advanced…** → copia el
campo **MAC Address** (las generadas por VMware empiezan por `00:0c:29`).
Anota junto a él la red (NAT, ACCESS o N6). Repite con cada adaptador.

Alternativa sin abrir diálogos: en el archivo `.vmx` de la VM (carpeta de la
VM en tu laptop) las líneas `ethernet0.generatedAddress`,
`ethernet1.generatedAddress`… tienen las MAC en el mismo orden que los
adaptadores de la pestaña Hardware.

**B) En la VM (qué nombre tiene ahora cada MAC).** Enciende la VM y:

```bash
ip -br link
# lo       UNKNOWN 00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP>
# ens33    UP      00:0c:29:aa:aa:aa <BROADCAST,MULTICAST,UP,LOWER_UP>
# ens37    DOWN    00:0c:29:bb:bb:bb <BROADCAST,MULTICAST>
# ens38    DOWN    00:0c:29:cc:cc:cc <BROADCAST,MULTICAST>
```

Las NIC nuevas aparecen `DOWN` y sin IP porque netplan todavía no las conoce.
Cruza las MAC con la lista de VMware y rellena esta tabla (guárdala, la vas a
necesitar en el paso siguiente y si algún día recreas una VM):

| VM | Red | MAC | Nombre actual | Nombre final |
|---|---|---|---|---|
| node-worker1 | access | `00:0c:29:__:__:__` | `ens3_` | `access` |
| node-worker2 | access | `00:0c:29:__:__:__` | `ens3_` | `access` |
| node-worker2 | n6 | `00:0c:29:__:__:__` | `ens3_` | `n6` |
| dn-gw | n6 | `00:0c:29:__:__:__` | `ens3_` | `n6` |

⚠️ Si dos NIC de una VM aparecen con la misma MAC, o una MAC no sale en
ninguna de las dos listas, para y revisa VMware (sección 6): no sigas con
netplan a ciegas.

---

## 9. Netplan: renombrar por MAC y asignar IP

Creamos un archivo **nuevo** en `/etc/netplan/`, separado del que dejó el
instalador (`00-installer-config.yaml`, que sigue gobernando `ens33`/mgmt).
Netplan junta todos los archivos de la carpeta por orden de nombre.

Reglas que valen para los tres nodos:

- `match.macaddress` elige la NIC por su MAC; `set-name` le pone el nombre
  final (`access` o `n6`). La clave de arriba (`access:`/`n6:`) es solo un
  identificador dentro del archivo; con `set-name` puede coincidir con el
  nombre final, que es lo más legible.
- `dhcp4: false` y `dhcp6: false`: en un LAN segment no hay DHCP, y un cliente
  esperando respuesta solo añade ruido y retrasos.
- `link-local: []`: tampoco IPv6 link-local. Queremos la NIC **sin ninguna
  dirección** en los workers.
- `optional: true`: si no, `systemd-networkd-wait-online` puede retener el
  arranque hasta 2 minutos esperando a que la NIC "esté lista".
- Netplan 22.04 exige que los archivos sean legibles solo por root
  (`chmod 600`), si no avisa en cada `netplan apply`.
- MAC en **minúsculas** y entre comillas.

### 9.1 node-worker1 (access, sin IP)

```bash
sudo tee /etc/netplan/60-lab-nics.yaml >/dev/null <<'EOF'
# Redes del lab (Fase 0). mgmt sigue en 00-installer-config.yaml.
# access: LAN segment ACCESS. SIN IP: solo es el padre de la ipvlan de Multus.
network:
  version: 2
  ethernets:
    access:
      match:
        macaddress: "00:0c:29:bb:bb:bb"   # <- MAC de la NIC en ACCESS (sección 8)
      set-name: access
      dhcp4: false
      dhcp6: false
      link-local: []
      optional: true
EOF
```

### 9.2 node-worker2 (access y n6, sin IP)

```bash
sudo tee /etc/netplan/60-lab-nics.yaml >/dev/null <<'EOF'
# Redes del lab (Fase 0). mgmt sigue en 00-installer-config.yaml.
# access: LAN segment ACCESS (N2+N3). n6: LAN segment N6.
# Ninguna lleva IP: son el padre de las ipvlan de gNB y UPF.
network:
  version: 2
  ethernets:
    access:
      match:
        macaddress: "00:0c:29:bb:bb:bb"   # <- MAC de la NIC en ACCESS
      set-name: access
      dhcp4: false
      dhcp6: false
      link-local: []
      optional: true
    n6:
      match:
        macaddress: "00:0c:29:cc:cc:cc"   # <- MAC de la NIC en N6
      set-name: n6
      dhcp4: false
      dhcp6: false
      link-local: []
      optional: true
EOF
```

### 9.3 dn-gw (n6 con 10.10.6.1/24)

```bash
sudo tee /etc/netplan/60-lab-nics.yaml >/dev/null <<'EOF'
# Redes del lab (Fase 0). mgmt (ens33, salida a internet) sigue en
# 00-installer-config.yaml. n6: LAN segment N6, puerta de enlace de la red N6.
# La ruta hacia el pool de UE (10.45.0.0/16 via 10.10.6.30), ip_forward y el
# MASQUERADE los pone Ansible en la Fase 1.
network:
  version: 2
  ethernets:
    n6:
      match:
        macaddress: "00:0c:29:dd:dd:dd"   # <- MAC de la NIC en N6
      set-name: n6
      dhcp4: false
      dhcp6: false
      addresses:
        - 10.10.6.1/24
      optional: true
EOF
```

Sin `routes` a propósito: la ruta por defecto de dn-gw sigue siendo la de
mgmt (`192.168.100.2`), que es por donde sale a internet.

### 9.4 Aplicar (en los tres nodos)

```bash
sudo chmod 600 /etc/netplan/*.yaml
sudo netplan generate            # valida la sintaxis; no debe imprimir nada
sudo netplan apply
ip -br link
```

⚠️ **Si la NIC sigue con el nombre viejo** (`ens37` en vez de `access`): el
renombrado lo hace udev al "descubrir" la interfaz y `netplan apply` no
siempre consigue renombrar una NIC que ya existía. Es normal. Reinicia:

```bash
sudo reboot
```

Tras el reinicio el nombre tiene que ser el nuevo. Si tampoco así, revisa la
MAC del archivo (sección 14).

---

## 10. Verificación

### 10.1 En cada nodo: nombres e IP

```bash
ip -br link
ip -br a
```

Lo que tiene que salir:

| VM | `ip -br link` | `ip -br a` |
|---|---|---|
| node-master | `ens33 UP` | `ens33 192.168.100.10/24` |
| node-worker1 | `ens33 UP`, `access UP` | `ens33 192.168.100.11/24`; **`access` sin ninguna IP** |
| node-worker2 | `ens33 UP`, `access UP`, `n6 UP` | `ens33 192.168.100.12/24`; **`access` y `n6` sin ninguna IP** |
| dn-gw | `ens33 UP`, `n6 UP` | `ens33 192.168.100.13/24`; `n6 10.10.6.1/24` |

- `UP` en `access`/`n6` sin IP es correcto: netplan levanta el enlace aunque no
  tenga direcciones. Si sale `DOWN`, la NIC no está conectada en VMware
  (*Connect at power on*) o el archivo no la ha "cogido" (MAC mal).
- Si en un worker `access` o `n6` muestran una IP `fe80::…`, falta
  `link-local: []`.

Comprueba también que el nombre quedó fijado por MAC y no por casualidad:

```bash
ip -br link | grep -E '^(access|n6) ' ; grep -h macaddress /etc/netplan/60-lab-nics.yaml
```

Las MAC de ambas salidas deben coincidir.

### 10.2 Entre nodos: ¿están de verdad en el mismo LAN segment?

Las NIC de los workers no tienen IP, así que para probar el cable les ponemos
una **temporal** y la quitamos al terminar. Esto no se queda configurado.

**ACCESS (worker1 ↔ worker2):**

```bash
# en node-worker1
sudo ip addr add 10.10.0.11/24 dev access
# en node-worker2
sudo ip addr add 10.10.0.12/24 dev access
ping -c 3 10.10.0.11                 # debe responder
# limpiar, en los dos
sudo ip addr del 10.10.0.11/24 dev access      # worker1
sudo ip addr del 10.10.0.12/24 dev access      # worker2
```

**N6 (worker2 ↔ dn-gw):**

```bash
# en node-worker2 (usamos la futura IP N6 del UPF, para que no choque con nada)
sudo ip addr add 10.10.6.30/24 dev n6
ping -c 3 10.10.6.1                  # dn-gw debe responder
sudo ip addr del 10.10.6.30/24 dev n6
```

**Aislamiento (debe fallar):** desde tu laptop, `ping 10.10.6.1` **no** debe
responder: el host no tiene adaptador en los LAN segments. Y desde
node-master (que no tiene pata en access ni en n6) tampoco.

Si todo lo anterior responde como se espera, la Fase 0 está terminada en lo
que a red se refiere.

### 10.3 Desde el laptop: SSH a las cuatro VMs

```bash
ssh bryantxz10@192.168.100.10 hostname     # node-master
ssh bryantxz10@192.168.100.11 hostname     # node-worker1
ssh bryantxz10@192.168.100.12 hostname     # node-worker2
ssh bryantxz10@192.168.100.13 hostname     # dn-gw
```

---

## 11. Plan B: `deploy_multus: false`

El interruptor `deploy_multus` de `ansible/group_vars/all.yml` elige la
arquitectura:

| | `deploy_multus: true` (tres redes, esta guía) | `deploy_multus: false` (plan B, una red) |
|---|---|---|
| Redes necesarias | mgmt, access, n6 | **solo mgmt** |
| NIC en workers | mgmt + access (+ n6 en worker2) | mgmt; `access`/`n6` pueden existir, nadie las usa |
| dn-gw | router N6, grupo `[dn]` del inventario | **no hace falta**: puedes dejarla apagada |
| N2, N3, N6 | por ipvlan sobre access/n6 (Multus) | por la red de pods de Cilium, como en el lab v2 |
| Lo que ve Cilium/Hubble | SBI, N4, DNS (lo de mgmt) | todo, incluidos N2/N3 |

Con `false` **no tienes que deshacer nada** de esta guía: las NIC sin IP no
molestan y dn-gw puede quedarse apagada (o comentada en el inventario para
que `ansible all -m ping` no falle por ella). Es la red de seguridad si
Multus/ipvlan da problemas antes de la charla.

> Estado del playbook: la arquitectura de tres redes ya está en `site.yml`
> (Fase 1: ipvlan, un NAD por NF, dn-gw), pero **no se ha verificado en
> clúster**. Despliega primero con `false` y pasa a `true` siguiendo
> [`docs/pruebas-fase1.md`](pruebas-fase1.md).

---

## 12. Inventario de Ansible

El inventario ya trae las cuatro VMs con el usuario `bryantxz10`:

```ini
[master]
node-master ansible_host=192.168.100.10 ansible_user=bryantxz10

[workers]
node-worker1 ansible_host=192.168.100.11 ansible_user=bryantxz10
node-worker2 ansible_host=192.168.100.12 ansible_user=bryantxz10

[dn]
dn-gw ansible_host=192.168.100.13 ansible_user=bryantxz10

[cluster:children]
master
workers
```

- `[dn]` queda **fuera** de `cluster`: los plays de k3s y Cilium apuntan a
  `cluster`, así que dn-gw nunca recibirá k3s por error.
- Las IP de access/n6 no van en `hosts.ini`: `ansible_host` es la de mgmt
  (k3s la usa como `--node-ip`). Lo demás está en `group_vars/all.yml` (IP
  fijas de AMF, gNB, UPF, dn-gw, pool de UE) y en `host_vars/<vm>.yml`
  (nombre de las NIC por nodo; en dn-gw, la IP de n6 y la ruta al pool).

Desde el nodo de control (el propio `node-master`, como en el lab v2, o tu
laptop con WSL2; ver `ansible/README-ansible.md`):

```bash
# llave SSH hacia las 4 VMs (pide la contraseña de bryantxz10 una vez por VM)
ssh-keygen -t ed25519            # si no tienes llave; Enter a todo
for h in 192.168.100.10 192.168.100.11 192.168.100.12 192.168.100.13; do
  ssh-copy-id -o StrictHostKeyChecking=accept-new bryantxz10@$h
done

git clone https://github.com/BryanTxz10/kcd-porto-5g-zero-trust-lab.git
cd kcd-porto-5g-zero-trust-lab/ansible
ansible-inventory --graph        # debe listar @cluster (master, workers) y @dn
ansible all -m ping              # 4 × SUCCESS / "ping": "pong"
```

Con eso Ansible ya llega a todo. **El despliegue (`ansible-playbook site.yml`)
es la Fase 1**: sigue [`docs/pruebas-fase1.md`](pruebas-fase1.md).

---

## 13. Snapshot y qué sigue

Apaga las cuatro VMs (`sudo poweroff`) y toma un snapshot en cada una con el
nombre `fase0-redes-ok`. Si algo se rompe en las fases siguientes, vuelves
aquí en un minuto en vez de reinstalar.

Lo que viene (Fase 1, todo desde Ansible, sin pasos a mano; detalle y
pruebas en [`docs/pruebas-fase1.md`](pruebas-fase1.md)):

- Multus con ipvlan sobre `access`/`n6` y NAD con IPAM estático para AMF, gNB
  y UPF.
- Play `dn-gw`: `ip_forward`, ruta `10.45.0.0/16 via 10.10.6.30` y MASQUERADE
  por mgmt (variables en `host_vars/dn-gw.yml`).
- Values del AMF y del UPF con las IP de N2/N3/N6. El placement por sitio ya
  lo fijan los `nodeSelector` de los values y manifiestos; el taint del master
  está en `ansible/hardening.yml` (`--tags taint`).

---

## 14. Problemas frecuentes

| Síntoma | Causa | Arreglo |
|---|---|---|
| Tras `netplan apply` la NIC sigue siendo `ens37` | udev no renombra una interfaz que ya estaba levantada | `sudo reboot` (sección 9.4) |
| Tras reiniciar sigue `ens37` y no existe `access` | MAC del archivo no coincide con la real | `ip -br link` vs `grep macaddress /etc/netplan/60-lab-nics.yaml`; ojo con mayúsculas y con copiar la MAC de otra VM |
| `access`/`n6` en `DOWN` | NIC desconectada en VMware o no gestionada por netplan | VM Settings → *Connect at power on*; revisa la MAC |
| `access` tiene una IP `fe80::…` | falta `link-local: []` | añádelo y `netplan apply` |
| El arranque tarda 2 minutos más | `systemd-networkd-wait-online` espera a una NIC sin `optional: true` | añade `optional: true` a esa NIC |
| `netplan generate` se queja de permisos | archivos legibles por todos | `sudo chmod 600 /etc/netplan/*.yaml` |
| En VMware no aparece *LAN segment* | el adaptador está en un tipo que no lo ofrece | selecciona el adaptador y mira *Network connection*; crea los segmentos con **LAN Segments…** (sección 2) |
| El clon arranca con IP `.10` | no editaste el netplan del instalador | sección 7, paso 2 |
| `ping 10.10.0.12` entre workers no responde | las dos NIC no están en el mismo LAN segment, o una está en `N6` | compara los segmentos en VMware; la MAC te dice cuál es cuál |
| `ansible all -m ping` falla solo en dn-gw | VM apagada o llave SSH sin copiar | enciéndela / `ssh-copy-id bryantxz10@192.168.100.13`; con `deploy_multus: false` puedes comentar dn-gw en el inventario |
| Nombre `ens33` distinto en mgmt (p. ej. `ens32`) | depende del slot PCI del primer adaptador | usa el nombre que salga en `ip -br a`; en `host_vars/dn-gw.yml` ajusta `mgmt_iface` |

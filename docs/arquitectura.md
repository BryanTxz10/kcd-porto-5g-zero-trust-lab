# Arquitectura del lab: un core 5G como lo despliega un operador

Este lab intenta parecerse lo más posible a un despliegue real de un operador, dentro
de lo que cabe en un laptop: cuatro VMs, tres redes agrupadas por zona de confianza y
el plano de usuario separado del plano de control. Este documento explica qué se
copia de los operadores, qué no y por qué.

> **Estado de verificación.** Esta arquitectura **no se ha desplegado aún de punta a
> punta**. Lo que está probado y lo que no se indica en cada `docs/pruebas-faseN.md`.

## 1. Vista general

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

| Red | En VMware | Qué viaja | Quién la controla |
|---|---|---|---|
| **mgmt / clúster** | VMnet8 (NAT) | Kubernetes, SBI (HTTP/2), N4 (PFCP), DNS, radio simulada (RLS UE↔gNB) | Cilium (políticas, identidad, Hubble) |
| **access** | LAN segment `ACCESS` | N2 (NGAP/SCTP) y N3 (GTP-U) | L2 aislado, admisión (Kyverno), MultiNetworkPolicy — Fase 2 |
| **n6** | LAN segment `N6` | tráfico de los UE hacia internet o la red de datos | dn-gw (CGNAT y firewall), Fase 2 |

IPs fijas: AMF 10.10.0.10, gNB 10.10.0.20, UPF 10.10.0.30 (N3) y 10.10.6.30 (N6),
dn-gw 10.10.6.1. Todas en `ansible/group_vars/all.yml`.

El interruptor `deploy_multus` elige entre esta arquitectura (`true`) y el **plan B**
(`false`): una sola red, todo por la red de pods de Cilium.

## 2. Por qué tres redes y no una

La agrupación es por **zona de confianza**, como hacen los operadores:

- **Lo que viene de la radio** (access). N2 y N3 llegan desde sitios de radio que el
  operador no controla físicamente del todo. Es la frontera más expuesta.
- **Lo interno del core** (mgmt). SBI y N4 entre funciones del core.
- **Lo que sale a internet** (n6). El tráfico de los suscriptores, que nunca debería
  poder tocar el core.

Con una sola red (plan B), un pod comprometido en cualquier namespace está a un
salto de L3 de todo, y la única barrera es la política de Cilium. Con tres redes, la
radio y la salida a internet viajan por interfaces que el CNI **no ve**: es el giro 1
de la charla. A cambio, la decisión de quién se conecta a la red de acceso pasa a ser
una decisión de **admisión** (Fase 2), no de red.

## 3. Comparación con operadores

### DISH Wireless (core 5G sobre AWS)

| DISH | Este lab |
|---|---|
| AMF y SMF en la Región de AWS (sitio central) | `node-worker1`: plano de control en `5g-cp` |
| UPF y CU en la Local Zone, con salida a internet local | `node-worker2`: UPF en `5g-up`, gNB/UE en `5g-ran`; N6 sale por dn-gw, junto al borde |
| Una VPC por sitio, aislamiento con tablas de rutas del Transit Gateway | Una red por zona de confianza (LAN segments); N4 cruza de sitio por Cilium |

### O2 Telefónica (core 5G sobre AWS)

| O2 Telefónica | Este lab |
|---|---|
| Multus y ENI en varias VPC para separar tráfico de control y de usuario | Multus con ipvlan sobre NIC dedicadas `access` y `n6` |

Fuentes:

- AWS for Industries, *Telco meets AWS cloud: deploying DISH's 5G network in AWS
  cloud*:
  <https://aws.amazon.com/blogs/industries/telco-meets-aws-cloud-deploying-dishs-5g-network-in-aws-cloud>.
  Sitios en Local Zones para el plano de usuario, VPC por sitio interconectadas con
  Transit Gateway y tablas de rutas que aíslan el tráfico entre funciones.
- AWS re:Invent 2022, TLC306, *DISH's 5G wireless deployment on AWS: From Region to
  edge*:
  <https://d1.awsstatic.com/events/Summits/reinvent2022/TLC306_DISHs-5G-wireless-deployment-on-AWS-From-Region-to-edge.pdf>.
- AWS for Industries, *O2 Telefónica moves its 5G core network to the cloud with AWS
  and Nokia*:
  <https://aws.amazon.com/blogs/industries/o2-telefonica-moves-its-5g-core-network-to-the-cloud-with-aws-and-nokia>.
  ENI en varias VPC para separar tipos de tráfico y Multus en Amazon EKS para el
  aislamiento entre redes.

Son publicaciones de AWS de alto nivel: describen la arquitectura, no la
configuración exacta de cada pod o subred.

### Diferencias que siguen y se declaran

| Diferencia | En un operador | Aquí | Por qué |
|---|---|---|---|
| Un solo clúster | Clústeres por sitio | Un k3s con nodos por sitio | Un laptop; el placement por `nodeSelector` imita los sitios |
| gNB dentro del clúster | gNB/CU fuera, en el sitio de radio | UERANSIM como pod en `5g-ran` | No hay radio real |
| N2 y N3 en la misma red sin VLAN | Separadas por VLAN o VRF | Misma red `access`; la separación se **declara**, no se implementa | Sencillez del lab |
| Sin IPsec en N2/N3 | TS 33.501 §9.2 y §9.3: obligatorio de implementar, opcional de usar | Fuera de alcance | Se declara en la Fase 2 |
| Radio simulada por la red de pods | — | RLS UE↔gNB por Cilium | Artefacto de UERANSIM |
| Un solo PLMN, sin roaming | SEPP y N32 | SEPP apagado | Red privada de un PLMN |

## 4. Mapa de fases

| Fase | Qué añade | Pruebas |
|---|---|---|
| 0 | VMs, redes y SO | [`guia-vms-realista.md`](guia-vms-realista.md) |
| 1 | Redes dedicadas con Multus y dn-gw | [`pruebas-fase1.md`](pruebas-fase1.md) |
| 2 | Controles en las redes dedicadas: L2, Kyverno, MultiNetworkPolicy | [`pruebas-fase2.md`](pruebas-fase2.md) |
| 3 | Cilium para lo que queda en la red de pods; WireGuard entre nodos | [`pruebas-fase3.md`](pruebas-fase3.md) |
| 4 | mTLS en la SBI (`sbi_tls`) | [`pruebas-fase4.md`](pruebas-fase4.md) |
| 5 | Spec-as-policy y blast radius map | [`pruebas-fase5.md`](pruebas-fase5.md) |
| 6 | Tetragon: cortar en el kernel | [`pruebas-fase6.md`](pruebas-fase6.md) |

## 5. Escenarios de la demo

| Escenario | Dónde ocurre | Qué lo para | Cómo se ve | Fase |
|---|---|---|---|---|
| **A1** movimiento lateral desde 5g-ran hacia la SBI | red de pods | Cilium: default deny + SBI solo entre identidades de NF | Hubble: `Policy denied DROPPED` | 3 |
| **A2** suplantar al NRF / pod impostor en 5g-cp | red de pods | Cilium: el impostor no tiene identidad de NF; admisión para las etiquetas | Hubble: DROPPED | 3 (y admisión) |
| **A3** desde un pod atacante que pide la red `access` | API server | Kyverno: el pod no llega a existir | `kubectl apply` → `denied the request` | 2 |
| **A3** desde el gNB comprometido | red `access` | Nada: la MultiNetworkPolicy permite el origen. *La política decide quién, no cuánto* | carga en el AMF | 2 |
| **UE contra el core** desde `uesimtun0` | N6 | dn-gw: el pool de UE no alcanza redes privadas; no toca la red de pods | `tcpdump -ni n6` en dn-gw, contador DROP | 1–2 |
| **Petición no autorizada al NRF** | SBI | L7 de Cilium en claro (403); con mTLS, L7 ciega | `make demo-l7-ciega` + Hubble | 3–4 |
| **Compromiso del AMF** (shell dentro) | kernel del nodo | Tetragon: Sigkill antes del `exec` | `make demo-tetragon` + `tetra getevents` | 6 |


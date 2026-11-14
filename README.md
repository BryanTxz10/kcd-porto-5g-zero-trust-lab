# kcd-porto-5g-zero-trust-lab

Laboratorio de la charla **"Zero Trust en un core 5G cloud native"** (KCD Porto,
19–20 de noviembre de 2026). Es un core 5G SA open source (Open5GS) sobre
Kubernetes, desplegado como lo haría un operador: plano de control en un sitio
central, plano de usuario en el borde y la radio y la salida a internet por redes
dedicadas. Sirve para ver dónde funciona una política Zero Trust y dónde deja de
funcionar.

## La charla en cinco pasos

1. **Punto de partida.** Una política de red de Cilium corta el movimiento lateral
   dentro de la SBI del core.
2. **Giro 1: lo que el CNI no ve.** La radio (N2, N3) y la salida a internet (N6)
   viajan por redes dedicadas con Multus, como en un operador, y Cilium deja de
   verlas. Quién se conecta a la red de acceso pasa a ser una decisión de
   **admisión** (Kyverno).
3. **Giro 2: mTLS te deja ciego.** Al cifrar la SBI con mTLS, como pide TS 33.501,
   la política L7 ya no puede decidir por método ni por ruta.
4. **Respuesta 1: spec-as-policy.** La política se deriva de la especificación
   3GPP, no de lo que se observa.
5. **Respuesta 2: cortar en el kernel.** Tetragon mata una shell dentro del AMF antes
   de que se ejecute, aunque el tráfico vaya cifrado.

## Arquitectura

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

| Red | Qué viaja | Quién la controla |
|---|---|---|
| mgmt / red de pods | Kubernetes, SBI (HTTP/2), N4 (PFCP), DNS, radio simulada | Cilium y Hubble |
| access (LAN segment) | N2 (NGAP/SCTP) y N3 (GTP-U) | aislamiento L2, Kyverno, MultiNetworkPolicy |
| n6 (LAN segment) | tráfico de los UE hacia internet | dn-gw (CGNAT y firewall) |

Con `deploy_multus: false` todo viaja por la red de pods: es el plan B, con tres VMs
y una sola red. Comparación con despliegues reales (DISH y O2 Telefónica sobre AWS)
y diferencias que se asumen: [`docs/arquitectura.md`](docs/arquitectura.md).

| Componente | Versión |
|---|---|
| k3s | v1.28.5+k3s1 |
| Cilium | 1.15.4 (kube-proxy replacement, VXLAN, Hubble) |
| Open5GS | 2.7.5, chart OCI de Gradiant 2.3.4 |
| UERANSIM | v3.2.6 |
| Multus | v4.0.2 (thick) |
| Kyverno | chart 3.1.4 |
| Tetragon | chart 1.1.2 |

## Cómo levantarlo

Guía completa: [`docs/guia-lab-desde-cero.md`](docs/guia-lab-desde-cero.md). En
resumen:

1. Crear las VMs y las redes en VMware:
   [`docs/guia-vms-realista.md`](docs/guia-vms-realista.md).
2. En `node-master`, instalar Ansible, copiar la llave SSH a las VMs y clonar el repo.
3. Desplegar con una sola red y comprobar:

   ```bash
   cd kcd-porto-5g-zero-trust-lab/ansible
   ansible-playbook site.yml -K
   cd .. && make smoke
   ```

4. Activar de uno en uno los interruptores de `ansible/group_vars/all.yml` y
   relanzar el playbook:

| Interruptor | Qué activa | Pruebas |
|---|---|---|
| `deploy_multus: true` | redes dedicadas, dn-gw, admisión con Kyverno, MultiNetworkPolicy | [fase 1](docs/pruebas-fase1.md), [fase 2](docs/pruebas-fase2.md) |
| `sbi_tls: true` | mTLS en la SBI con una CA generada en el despliegue | [fase 4](docs/pruebas-fase4.md) |
| `node_encryption: true` | WireGuard entre nodos | [fase 3](docs/pruebas-fase3.md) |
| `deploy_tetragon` (activo) | Tetragon y sus políticas | [fase 6](docs/pruebas-fase6.md) |

Las políticas de Cilium del modo elegido se aplican al final de cada despliegue
([fase 3](docs/pruebas-fase3.md)). Ninguna clave ni certificado vive en el repo: se
generan al desplegar.

## Demos

| Comando | Qué se ve |
|---|---|
| `make policy-matrix` | sin clúster: qué flujos permite o corta Cilium en cada modo |
| `bash attacks/a1-movimiento-lateral.sh` | un pod comprometido en la RAN no alcanza ningún servicio del core |
| `bash attacks/a2-nrf-desde-la-ran.sh` | el mismo pod no puede registrar, desviar ni borrar NF en el NRF |
| `bash attacks/a2-nrf-desde-impostor.sh` | un impostor dentro de `5g-cp` tampoco: el namespace no da identidad |
| `kubectl apply -f attacks/attacker-access.yaml` | el API server rechaza un pod que pide la red de la radio |
| `AMF_IP=10.10.0.10 ORIGEN=gnb bash attacks/a3-flood-n2.sh` | un gNB comprometido sí inunda N2: la política decide quién, no cuánto |
| `make demo-l7-ciega` | la misma petición no autorizada al NRF: 403 en claro, sin visibilidad con mTLS |
| `make demo-tetragon` | una shell dentro del AMF muere antes de ejecutarse |
| `make spec2policy` | políticas L7 y blast radius map derivados de la OpenAPI 3GPP |

Antes de los ataques: `kubectl apply -f attacks/attacker-ran.yaml` (y
`attacks/nf-impostor.yaml` para el impostor). Qué para cada escenario:
[`docs/arquitectura.md`](docs/arquitectura.md) §5.

## Blast radius map

`tools/spec2policy/` deriva de la OpenAPI 3GPP (Rel-17) y de TS 23.501 qué
operaciones de la SBI puede pedir cada NF, lo cruza con los flujos reales de Hubble
y produce un informe en Markdown y CSV con lo que permite el estándar, lo que se
observó y la diferencia. No necesita clúster.

| | |
|---|---|
| Plantilla vacía para rellenar con tu captura | [`docs/blast-radius-map-plantilla.md`](docs/blast-radius-map-plantilla.md) · [`.csv`](docs/blast-radius-map-plantilla.csv) |
| Ejemplo con flujos sintéticos | [`tools/spec2policy/examples/out/blast-radius-map.md`](tools/spec2policy/examples/out/blast-radius-map.md) |
| Cómo capturar flujos reales | [`docs/pruebas-fase5.md`](docs/pruebas-fase5.md) |

## Estado

El CI valida todo estáticamente en cada push: shellcheck, yamllint, ansible-lint,
kustomize, ruff, la matriz de políticas, los tests de spec2policy y los escáneres de
seguridad (gitleaks, actionlint, zizmor, trivy, checkov, kube-linter). Esta versión
del lab **todavía no se ha desplegado de punta a punta**. Cada
`docs/pruebas-faseN.md` dice qué está comprobado, qué no y cómo comprobarlo. Lo que
se presente como probado en la charla será lo que se haya visto funcionar.

## Estructura

```
.
├── ansible/            # despliegue (site.yml), hardening (hardening.yml) y plantillas
├── k8s/
│   ├── cilium/         # políticas de Cilium: base + overlay por modo
│   ├── multinetwork/   # MultiNetworkPolicy de las redes access y n6
│   ├── admission/      # políticas de Kyverno: redes dedicadas e identidad de NF
│   ├── tetragon/       # TracingPolicy de Tetragon
│   ├── helm-values/    # values del chart de Open5GS (Gradiant)
│   ├── ueransim/       # configuración del gNB y del UE
│   └── manifests/      # UERANSIM, sbi-probe y el Service N2 del plan B
├── attacks/            # escenarios de ataque
├── scripts/            # prueba de humo, demos y matriz de políticas
├── tools/spec2policy/  # spec-as-policy y blast radius map
└── docs/               # arquitectura, guías y pruebas por fase
```

Integración continua y seguridad del pipeline:
[`docs/ci-cd-seguridad.md`](docs/ci-cd-seguridad.md). Réplica local: `make ci`.

## Licencia

[`LICENSE`](LICENSE).

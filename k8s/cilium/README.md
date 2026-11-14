# Políticas de Cilium

Lo que sigue en la red de pods, en los dos modos del interruptor `deploy_multus`:

| Overlay | Modo | Qué añade a `base/` |
|---|---|---|
| `una-red/` | `deploy_multus: false` (plan B) | N2 (gNB→AMF, SCTP 38412), N3 (gNB↔UPF, UDP 2152) y la salida del UPF a `world` (N6) |
| `multus/` | `deploy_multus: true` | nada: N2, N3 y N6 van por Multus y los controla la Fase 2. El egress del UPF en la red de pods queda vacío |
| `una-red-tls/`, `multus-tls/` | lo mismo con `sbi_tls: true` | el componente `components/sbi-tls` quita las reglas `http` del NRF: con mTLS el proxy L7 no puede leer la petición (Fase 4) |

`base/` (los dos modos):

| Fichero | Qué hace |
|---|---|
| `00-default-deny.yaml` | default deny de ingress y egress en 5g-cp, 5g-ran y 5g-up |
| `01-sbi-identidad.yaml` | SBI (TCP 7777) solo entre las identidades de las NF del core |
| `02-nrf-sbi-l7.yaml` | NRF: solo las operaciones de TS 29.510 (L7, da visibilidad HTTP a Hubble) |
| `03-mongodb.yaml` | MongoDB solo desde UDR, PCF y populate |
| `04-egress-cp.yaml` | 5g-cp solo habla consigo mismo y con el DNS; sin `world` |
| `05-n4.yaml` | N4 (PFCP, UDP 8805) solo del SMF al UPF |
| `06-ran.yaml` | RLS UE↔gNB dentro de 5g-ran y DNS |
| `07-sbi-probe.yaml` | el pod de prueba `sbi-probe` solo llega al NRF, y sin TLS solo para `GET /nnrf-disc/v1/nf-instances` |

Aplicar: `make policies` (elige el overlay según `deploy_multus` y `sbi_tls` de
`ansible/group_vars/all.yml`) o `ansible-playbook site.yml --tags policies`.
Comprobar sin clúster: `make policy-matrix`. Pruebas: `docs/pruebas-fase3.md`.

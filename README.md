# kcd-porto-5g-zero-trust-lab — Zero Trust en un core 5G cloud native

Laboratorio de demostración para una charla de 30 min en **KCD Porto (19–20 nov 2026)**
sobre cómo aplicar (y dónde se rompe) un enfoque Zero Trust en el plano de señalización
de un núcleo 5G SA open source desplegado sobre Kubernetes.

> **Origen.** Este repositorio nace de
> [`BryanTxz10/cib46-zta-5g-core`](https://github.com/BryanTxz10/cib46-zta-5g-core),
> conservando su historial. Allí vivía el testbed de la tesis CIB46; aquí se reorienta
> el mismo código hacia la charla y se archiva en [`legacy/`](legacy/) el material
> exclusivamente académico (protocolo experimental, análisis estadístico,
> `data-processing/`, transiciones imperativas `transition-to-c*.sh`, `REPRODUCIBILITY.md`
> y `CITATION.cff`). Ese material **no se mantiene ni se valida en CI**.

## El arco de la charla

1. **Punto de partida.** Una política de red (Cilium L3/L4) bloquea el movimiento
   lateral dentro de la SBI (*Service Based Interface*) del core.
2. **Giro 1 — lo que el CNI no ve.** El radio (N2/N3) y la salida a internet del UPF
   (N6) viajan por redes dedicadas con **Multus**; esas interfaces quedan fuera del
   alcance del CNI, así que la política que creías total no las cubre.
   Quién se conecta a la red de acceso pasa a ser una decisión de **admisión**
   (Kyverno), con MultiNetworkPolicy en esas interfaces. Pruebas:
   [`docs/pruebas-fase1.md`](docs/pruebas-fase1.md) y
   [`docs/pruebas-fase2.md`](docs/pruebas-fase2.md).
3. **Giro 2 — mTLS te deja ciego.** Al cifrar la SBI con **mTLS**, la política L7
   basada en inspección HTTP se queda sin visibilidad: ya no puede decidir por método
   ni por ruta. Interruptor `sbi_tls`; demo con `make demo-l7-ciega`. Pruebas:
   [`docs/pruebas-fase4.md`](docs/pruebas-fase4.md).
4. **Respuesta 1 — spec-as-policy.** Derivar la política directamente de la
   especificación 3GPP de la SBI, para autorizar por identidad y contrato de API en
   lugar de por inspección de paquetes.
5. **Respuesta 2 — cortar en el kernel.** **Tetragon** observa y corta en el punto de
   ejecución (eBPF/kernel), por debajo del cifrado de la capa de transporte.

> **Estado de verificación.** El material de este repo (manifiestos, políticas,
> scripts) **no se ha validado end-to-end en clúster dentro de este repositorio**.
> Lo que se afirme como probado en la charla se marcará explícitamente; el resto es
> diseño/propuesta. El CI solo valida *estáticamente* (lint, sintaxis, build de
> manifiestos), no despliegue real.

## Stack tecnológico

| Componente | Versión |
|---|---|
| k3s (Kubernetes) | v1.28.5 |
| Open5GS | v2.7 (lab v2: 2.7.5, chart Gradiant 2.3.4) |
| Cilium (CNI) | v1.15.4 |
| Multus | v4.0.2 |
| UERANSIM | v3.2.6 |
| SPIRE | 1.8.5, integrado en Cilium (mutual authentication, beta) |

**Montar el lab desde VMs vacías:** [`docs/guia-lab-desde-cero.md`](docs/guia-lab-desde-cero.md)

## Estructura del repositorio

```
.
├── ansible/             # Despliegue declarativo con Ansible (recomendado) + guía desde cero
├── bootstrap/           # Despliegue con bash (respaldo) y checks del plano de control
├── cilium-policies/     # CiliumNetworkPolicy por capa + overlays Kustomize (conditions/)
├── multinetwork-policies/ # MultiNetworkPolicy de las redes dedicadas access y n6 (Fase 2)
├── helm-values/         # values.yaml del chart Open5GS (Gradiant)
├── attack-scripts/      # Scripts de los vectores de ataque (movimiento lateral, spoofing, flood)
├── spire-config/        # SPIRE autónomo de la v1 (legado; en lab v2 SPIRE lo instala Cilium)
├── monitoring/          # Consultas de monitoreo de recursos del AMF
├── ueransim-config/     # Configuración de UERANSIM (gNB y UEs)
├── tools/spec2policy/   # Fase 5: CNP L7 y blast radius map derivados de la OpenAPI 3GPP
├── docs/                # Arquitectura, guías de laboratorio y estado del arte
└── legacy/              # Material de la tesis, archivado y NO mantenido (ver legacy/README.md)
```

## Despliegue automatizado

Dos caminos equivalentes (versiones fijadas, idempotentes):

| Camino | Comando | Para |
|---|---|---|
| **Ansible** (declarativo, recomendado) | `cd ansible && ansible-playbook site.yml` | ver `ansible/README-ansible.md` (desde cero) |
| **Bash** (imperativo, respaldo) | `make up` | prototipado rápido; ver `docs/guia-reproducibilidad.md` |

> No verificado end-to-end en este repositorio. Trátese como procedimiento de
> referencia hasta reproducirlo en un clúster.

## Integración continua y seguridad del pipeline

Cada push y PR a `main` dispara dos workflows de GitHub Actions que verifican el
material **estáticamente** antes de cualquier despliegue:

| Workflow | Valida |
|---|---|
| `CI — Validación de despliegue` | bash (shellcheck/`bash -n`), Ansible (`--syntax-check` + lint), Kustomize (`build` de las capas), Python (compileall + ruff) |
| `Seguridad CI/CD` | secretos (gitleaks), seguridad de workflows (actionlint/zizmor), IaC/K8s (trivy/checkov/kube-linter) |

El pipeline aplica mínimo privilegio (`permissions: contents: read`), acciones
fijadas por SHA y escaneo de secretos bloqueante. La carpeta `legacy/` queda
**fuera del alcance de los linters** por estar deprecada. Detalle y roles de
seguridad: `docs/ci-cd-seguridad.md`. Réplica local: `make ci`.

## Políticas de Cilium (Fase 3)

Lo que queda en la red de pods lo protege Cilium con una base común y un overlay
por modo (`cilium-policies/lab/`):

| | Plan B (`deploy_multus: false`) | Redes dedicadas (`true`) |
|---|---|---|
| Default deny de ingress y egress, SBI solo entre identidades de NF, NRF con L7, N4 solo SMF→UPF, MongoDB restringido, 5g-cp sin `world`, RLS dentro de 5g-ran | ✔ | ✔ |
| N2, N3 y salida del UPF a `world` | en Cilium | por Multus (Fase 2); el UPF no tiene egress en la red de pods |

El playbook aplica el overlay del modo al final; a mano, `make policies`. Con
`sbi_tls: true` se aplica la variante `-tls`, sin las reglas L7 (Fase 4). Sin
clúster, `make policy-matrix` evalúa los flujos legítimos y de ataque en los dos
modos (aproximación L3/L4; también en CI). Cifrado entre nodos con WireGuard:
`node_encryption: true`. Pruebas: [`docs/pruebas-fase3.md`](docs/pruebas-fase3.md).

Las capas `cilium-policies/conditions/c0…c3` son las de la tesis y se conservan solo
como referencia (`make condition C=…`).

## Spec-as-policy y blast radius map (Fase 5)

`tools/spec2policy/` deriva las CiliumNetworkPolicy L7 de la SBI a partir de la
OpenAPI 3GPP y de la tabla de consumidores de TS 23.501, las cruza con flujos de
Hubble y produce un **blast radius map**: qué operaciones permite el estándar, cuáles
se observaron y desde qué origen. No necesita clúster.

| Qué | Dónde |
|---|---|
| Generar y probar | `make spec2policy` · `make spec2policy-test` |
| Guía de pruebas (qué debe verse, cómo capturar flujos reales) | [`docs/pruebas-fase5.md`](docs/pruebas-fase5.md) |
| Ejemplo con flujos **sintéticos** | [`tools/spec2policy/examples/out/blast-radius-map.md`](tools/spec2policy/examples/out/blast-radius-map.md) |
| Plantilla para la captura real en el clúster | [`docs/blast-radius-map-plantilla.md`](docs/blast-radius-map-plantilla.md) · [`.csv`](docs/blast-radius-map-plantilla.csv) |

La plantilla está vacía a propósito: se rellena con la salida de una captura real,
que aún no se ha hecho (ver *Estado de verificación*).

## Licencia

Ver [`LICENSE`](LICENSE). El repositorio se publica con fines de divulgación y
reproducibilidad.

# kcd-porto-5g-zero-trust-lab

A 5G standalone core (Open5GS) running on Kubernetes, deployed the way an operator
would deploy it, and used as a stress test for Zero Trust in cloud native
infrastructure. It is the lab behind the talk **"Zero Trust for a cloud native 5G
core"** at KCD Porto (19–20 November 2026).

The goal is not to show that a network policy blocks traffic. It is to find
**where Zero Trust stops working**, and what has to take over at that point.

> Detailed guides and test plans under [`docs/`](docs/) are written in Spanish.
> Commands, file names and code comments are the same in both languages.

## The story in five steps

1. **Baseline.** A Cilium network policy stops lateral movement inside the core's
   service-based interface (SBI).
2. **Twist 1: what the CNI cannot see.** Radio traffic (N2, N3) and internet egress
   (N6) run on dedicated networks with Multus, as in an operator network, and
   Cilium no longer sees them. Who may join the radio network becomes an
   **admission** decision (Kyverno).
3. **Twist 2: mTLS makes you blind.** Encrypting the SBI with mTLS, as 3GPP TS 33.501
   requires, means the L7 policy can no longer decide on method or path.
4. **Answer 1: spec-as-policy.** Derive the policy from the 3GPP specification
   instead of from observed traffic.
5. **Answer 2: stop it in the kernel.** Tetragon kills a shell inside the AMF before
   it runs, even when all traffic is encrypted.

## Architecture

```
                     Laptop · VMware Workstation
   mgmt = VMnet8 (NAT) 192.168.100.0/24 · pods 10.42.0.0/16 (VXLAN) · Services 10.43.0.0/16
   ─────┬──────────────────────┬──────────────────────────┬──────────────────┬──────────
        │.10                   │.11                       │.12               │.13
 ┌──────┴──────┐  ┌────────────┴────────────┐  ┌──────────┴──────────┐  ┌────┴─────────┐
 │ node-master │  │ node-worker1            │  │ node-worker2        │  │ dn-gw        │
 │ k3s server  │  │ CENTRAL SITE            │  │ EDGE SITE           │  │ DATA NETWORK │
 │ (tainted)   │  │ 5g-cp: NRF SCP AMF SMF  │  │ 5g-up: UPF          │  │ N6 router    │
 │             │  │ AUSF UDM UDR PCF NSSF   │  │ 5g-ran: gNB, UE,    │  │ CGNAT +      │
 │             │  │ BSF, MongoDB            │  │ attackers           │  │ N6 firewall  │
 └─────────────┘  └────────────┬────────────┘  └───┬────────────┬────┘  └────┬─────────┘
                    AMF n2 .10 │          gNB .20  │  UPF n3 .30│ UPF n6 .30 │ n6 .1
   access 10.10.0.0/24 ────────┴───────────────────┘            │            │
   (N2 NGAP/SCTP + N3 GTP-U)                                    │            │
   n6 10.10.6.0/24 ─────────────────────────────────────────────┴────────────┘
   (subscriber traffic to the data network)                        UE pool 10.45.0.0/16
```

Control plane and user plane are split the way operators split them: control
plane functions at a central site, the UPF at the edge next to the radio, and each
plane in its own namespace and Helm release.

| Network | What it carries | What controls it |
|---|---|---|
| mgmt / pod network | Kubernetes, SBI (HTTP/2), N4 (PFCP), DNS, simulated radio | Cilium and Hubble |
| access (isolated LAN segment) | N2 (NGAP/SCTP) and N3 (GTP-U) | L2 isolation, Kyverno, MultiNetworkPolicy |
| n6 (isolated LAN segment) | subscriber traffic to the internet | dn-gw (CGNAT and firewall) |

With `deploy_multus: false` everything runs on the pod network instead. That is the
fallback: three VMs, one network, everything visible to Cilium.

How this compares with real deployments (DISH and O2 Telefónica on AWS), and what
the lab does not reproduce: [`docs/arquitectura.md`](docs/arquitectura.md).

| Component | Version |
|---|---|
| k3s | v1.28.5+k3s1 |
| Cilium | 1.15.4 (kube-proxy replacement, VXLAN, Hubble) |
| Open5GS | 2.7.5, Gradiant OCI chart 2.3.4 |
| UERANSIM | v3.2.6 |
| Multus | v4.0.2 (thick) |
| Kyverno | chart 3.1.4 |
| Tetragon | chart 1.1.2 |

## Quick start

Full walkthrough: [`docs/guia-lab-desde-cero.md`](docs/guia-lab-desde-cero.md).

1. Create the VMs and networks in VMware:
   [`docs/guia-vms-realista.md`](docs/guia-vms-realista.md).
2. On `node-master`, install Ansible, copy your SSH key to every VM and clone this
   repository.
3. Deploy with a single network first and check it:

   ```bash
   cd kcd-porto-5g-zero-trust-lab
   make up      # ansible-playbook site.yml -K
   make smoke   # UE registration + a legitimate SBI request
   ```

4. Turn on the switches in `ansible/group_vars/all.yml` one at a time, and run the
   playbook again after each one:

| Switch | What it enables | Test plan |
|---|---|---|
| `deploy_multus: true` | dedicated networks, dn-gw, Kyverno admission, MultiNetworkPolicy | [phase 1](docs/pruebas-fase1.md), [phase 2](docs/pruebas-fase2.md) |
| `sbi_tls: true` | mTLS on the SBI, with a CA generated at deploy time | [phase 4](docs/pruebas-fase4.md) |
| `node_encryption: true` | WireGuard between nodes | [phase 3](docs/pruebas-fase3.md) |
| `deploy_tetragon` (on by default) | Tetragon and its tracing policies | [phase 6](docs/pruebas-fase6.md) |

The Cilium policies for the selected mode are applied at the end of every run
([phase 3](docs/pruebas-fase3.md)). No keys or certificates live in this repository:
they are generated at deploy time.

## Demos

Deploy the attacker pods first:

```bash
kubectl apply -f attacks/attacker-ran.yaml   # compromised device on the radio side
kubectl apply -f attacks/nf-impostor.yaml    # impostor pod inside the core namespace
```

| Scenario | Command | Expected result | What stops it |
|---|---|---|---|
| Lateral movement from the RAN | `bash attacks/a1-movimiento-lateral.sh` | no core service reachable | Cilium: default deny, SBI only between NF identities |
| Hijack the NRF from the RAN | `bash attacks/a2-nrf-desde-la-ran.sh` | cannot register, redirect or delete NFs | Cilium |
| Hijack the NRF from inside the core | `bash attacks/a2-nrf-desde-impostor.sh` | same: a namespace is not an identity | Cilium identity, plus [admission](k8s/admission/) so labels cannot be copied |
| Join the radio network | `kubectl apply -f attacks/attacker-access.yaml` | the API server rejects the pod | Kyverno |
| N2 flood from a compromised gNB | `AMF_IP=10.10.0.10 ORIGEN=gnb bash attacks/a3-flood-n2.sh` | **gets through** | nothing: policy decides *who*, not *how much* |
| Unauthorized NRF request | `make demo-l7-ciega` | 403 in clear text; no L7 visibility with mTLS | Cilium L7, until the SBI is encrypted |
| Shell inside the AMF | `make demo-tetragon` | the process is killed before it runs | Tetragon |
| No cluster needed | `make policy-matrix` | which flows each mode allows or drops | — |

Scenario details: [`docs/arquitectura.md`](docs/arquitectura.md) §5.

## Blast radius map

`tools/spec2policy/` reads the 3GPP OpenAPI specifications (Rel-17) and TS 23.501
to work out which SBI operations each network function may call. It compares that
with the real flows captured by Hubble and produces a report, in Markdown and CSV,
with what the standard allows, what was observed and the difference. It generates
the matching L7 Cilium policies too, and runs without a cluster:

```bash
make spec2policy
```

| | |
|---|---|
| Empty template to fill in with your own capture | [`docs/blast-radius-map-plantilla.md`](docs/blast-radius-map-plantilla.md) · [`.csv`](docs/blast-radius-map-plantilla.csv) |
| Example built from synthetic flows | [`tools/spec2policy/examples/out/blast-radius-map.md`](tools/spec2policy/examples/out/blast-radius-map.md) |
| How to capture real flows | [`docs/pruebas-fase5.md`](docs/pruebas-fase5.md) |

## Status

CI checks everything statically on every push: shellcheck, yamllint, ansible-lint,
kustomize builds, ruff, the policy matrix, the spec2policy tests and security
scanners (gitleaks, actionlint, zizmor, trivy, checkov, kube-linter).

**This version of the lab has not yet been deployed end to end.** Each
`docs/pruebas-faseN.md` states what has been verified, what has not, and how to
verify it. Only what has been seen working will be presented as working.

## Repository layout

```
.
├── ansible/            # deployment (site.yml), hardening (hardening.yml), templates
├── k8s/
│   ├── cilium/         # Cilium policies: base + one overlay per mode
│   ├── multinetwork/   # MultiNetworkPolicy for the access and n6 networks
│   ├── admission/      # Kyverno policies: dedicated networks and NF identity
│   ├── tetragon/       # Tetragon TracingPolicies
│   ├── helm-values/    # Open5GS chart values (Gradiant)
│   ├── ueransim/       # gNB and UE configuration
│   └── manifests/      # UERANSIM, sbi-probe and the fallback N2 Service
├── attacks/            # attack scenarios
├── scripts/            # smoke test, demos and policy matrix
├── tools/spec2policy/  # spec-as-policy and blast radius map
└── docs/               # architecture, guides and per-phase test plans (Spanish)
```

CI and pipeline security: [`docs/ci-cd-seguridad.md`](docs/ci-cd-seguridad.md).
Run the CI checks locally with `make ci`.

## License

[MIT](LICENSE).

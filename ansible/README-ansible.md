# Despliegue con Ansible

Referencia rápida del playbook. El paso a paso desde VMs vacías está en
[`docs/guia-lab-desde-cero.md`](../docs/guia-lab-desde-cero.md), y la creación de las
VMs y las redes en [`docs/guia-vms-realista.md`](../docs/guia-vms-realista.md).

## Ficheros

| Fichero | Qué es |
|---|---|
| `site.yml` | despliegue completo e idempotente: k3s, Cilium, Multus, Kyverno, Open5GS, UERANSIM, Tetragon y políticas |
| `hardening.yml` | Pod Security Standards por namespace y taint del master; se lanza después de `site.yml` |
| `inventory/hosts.ini` | las VMs: `[master]`, `[workers]` y `[dn]` (dn-gw, fuera de `cluster`) |
| `group_vars/all.yml` | versiones, interruptores, IPs y nombres |
| `host_vars/<vm>.yml` | nombres de las NIC de cada VM; en dn-gw, la IP de n6 y la ruta al pool de UE |
| `templates/` | lo que se genera al desplegar: NAD, values extra del chart, patches, PKI de la SBI, script de NAT de dn-gw |

## Inventario

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

- `ansible_host` es la IP de mgmt: k3s la usa como `--node-ip`.
- Si tu usuario no es `bryantxz10`, cámbialo aquí.
- Las IPs de las redes `access` y `n6` no van en el inventario: están en
  `group_vars/all.yml`.
- Con `deploy_multus: false`, dn-gw no se usa y puede estar apagada. El play de
  dn-gw no se conecta en ese modo; si quieres que `ansible all -m ping` no falle,
  comenta su línea.

## Interruptores

| Variable | Por defecto | Qué hace |
|---|---|---|
| `deploy_multus` | `false` | redes dedicadas `access` y `n6` con Multus, dn-gw, Kyverno y MultiNetworkPolicy |
| `deploy_multi_networkpolicy` | `true` | MultiNetworkPolicy (solo con Multus) |
| `kyverno_multus_guard_action` | `Enforce` | `Audit` para observar sin bloquear |
| `apply_cilium_policies` | `true` | aplica `cilium-policies/lab/<modo>` al final |
| `node_encryption` | `false` | WireGuard entre nodos |
| `sbi_tls` | `false` | mTLS en la SBI; la CA y los certificados se generan en el master |
| `deploy_tetragon` | `true` | Tetragon y `tetragon-policies/` |
| `deploy_spire` | `true` | SPIRE integrado en Cilium |

## Uso

Desde esta carpeta:

```bash
ansible-inventory --graph
ansible all -m ping
ansible-playbook site.yml -K          # -K pide la contraseña de sudo
ansible-playbook hardening.yml -K
```

Solo una parte:

```bash
ansible-playbook site.yml -K --tags open5gs,ueransim
ansible-playbook site.yml -K --tags policies
```

| Tag | Qué repite |
|---|---|
| `prereqs` | paquetes, SCTP, swap |
| `k3s` | k3s server y agents |
| `cilium`, `spire` | Cilium (y SPIRE integrado) |
| `dn-gw` | router N6 |
| `multus` | rutas de CNI, plugins, Multus, NAD y patches del UPF y el gNB |
| `admission` | Kyverno y la política de redes dedicadas |
| `mnp` | multi-networkpolicy-iptables y las MultiNetworkPolicy |
| `open5gs` | UPF y plano de control |
| `tls` | PKI de la SBI, Secrets y `sbi-probe` |
| `ueransim` | gNB y UE |
| `tetragon` | Tetragon y sus políticas |
| `policies` | políticas de Cilium del modo elegido |

## Comprobaciones estáticas

Las mismas que el CI:

```bash
ansible-playbook -i inventory/hosts.ini site.yml --syntax-check
ansible-lint site.yml
```

## Problemas

| Síntoma | Causa | Qué hacer |
|---|---|---|
| `UNREACHABLE` | falta la llave SSH en esa VM | `ssh-copy-id <usuario>@<IP>` |
| `Missing sudo password` | falta `-K` | relanzar con `-K` |
| falla *Las rutas coinciden con las del master* | versiones distintas de k3s entre nodos | reinstalar el nodo con `k3s_version` |
| falla *Las IP de la política coinciden con group_vars* | se cambiaron IPs en `group_vars` sin actualizar la política de Kyverno | editar `kcd-multus-network-guard` en `bootstrap/admission/kyverno-identity-guard.yaml` |
| falla *El manifiesto tiene los ajustes* | el `deploy.yml` de multi-networkpolicy-iptables cambió de forma | revisar el manifiesto del tag fijado o `deploy_multi_networkpolicy: false` |

Más síntomas en [`docs/guia-lab-desde-cero.md`](../docs/guia-lab-desde-cero.md) §14.

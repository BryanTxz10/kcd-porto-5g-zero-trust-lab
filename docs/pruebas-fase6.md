# Pruebas — Fase 6: Tetragon, cortar en el kernel

Respuesta 2 de la charla. Cuando la SBI va cifrada (Fase 4), la red ya no puede
decidir por método ni por ruta. Tetragon actúa en otro sitio: en el kernel, sobre el
proceso. Si alguien ejecuta una shell dentro del AMF, Tetragon la mata antes de que
se ejecute y antes de que salga un solo paquete. Eso no depende de ver el tráfico.

> **Estado de verificación.**
> - Comprobado en local: yamllint, `ansible-lint`, `--syntax-check` y
>   `kustomize build k8s/tetragon`.
> - **No se ha ejecutado en un clúster.** No se ha comprobado que exista el chart
>   1.1.2, ni que las políticas carguen en esa versión, ni el comportamiento con el
>   entrypoint de Gradiant (§4).

## 1. Qué se despliega (`deploy_tetragon: true`)

| Pieza | Qué hace | Dónde |
|---|---|---|
| Tetragon | chart `cilium/tetragon` `tetragon_chart_version` (1.1.2, ⚠ por verificar) en kube-system, con `enablePolicyFilter=true` (necesario para `podSelector` y políticas por namespace) | `site.yml`, tag `tetragon` |
| `amf-sin-shell` (TracingPolicyNamespaced, 5g-cp) | Sigkill en `security_bprm_check` si un proceso del pod del AMF que **no** es el PID 1 del contenedor intenta ejecutar una shell (`sh`, `bash`, `dash`, `ash`, `zsh`, `busybox`) o una herramienta de red o de scripting (`curl`, `wget`, `nc`, `ncat`, `netcat`, `socat`, `nmap`, `telnet`, `ssh`, `python3`, `perl`) | `k8s/tetragon/00-amf-sin-shell.yaml` |
| `sockets-redes-dedicadas` (TracingPolicy) | Registra, sin acción, qué proceso hace `bind` o `connect` con una dirección de access (10.10.0.0/24) o n6 (10.10.6.0/24). Es la observabilidad que Hubble no da en las interfaces de Multus | `k8s/tetragon/01-sockets-redes-dedicadas.yaml` |

### La trampa del entrypoint

El entrypoint del chart de Gradiant es un script bash. Si la política matara
cualquier `bash` dentro del AMF, el contenedor no podría arrancar de nuevo tras un
reinicio. Se acota por PID:

- El arranque corre como **PID 1** del namespace de PID del contenedor (runc init →
  bash del entrypoint → `exec` del binario del AMF), y la política no actúa sobre
  el PID 1.
- Una shell de `kubectl exec`, o un hijo que lance el propio AMF comprometido
  (`fork` + `exec`), **nunca es el PID 1**, y esos procesos se matan.

Por la misma razón, el smoke y la demo de la SBI ya no hacen `curl` dentro del AMF:
salen del pod `sbi-probe` (Fase 4). La tarea de Ansible que comprueba las interfaces
de Multus usa `cat`, que no está en la lista.

## 2. Instalación

```bash
ansible-playbook site.yml -K --tags tetragon
kubectl -n kube-system get ds tetragon
kubectl get tracingpolicies
kubectl get tracingpoliciesnamespaced -n 5g-cp
```

## 3. Demo: compromiso del AMF (no ejecutado aún)

```bash
make demo-tetragon
```

Debe verse:

1. `kubectl exec … sh -c 'id'` no imprime nada y termina con `command terminated
   with exit code 137`, es decir, SIGKILL.
2. `kubectl exec … curl …` igual: 137, y ni un paquete hacia el NRF. Hubble no ve
   ese flujo, porque el proceso murió antes de abrir el socket.
3. Eventos de Tetragon parecidos a estos (cópialos del lab, no de aquí):

   ```
   🚀 process 5g-cp/open5gs-cp-amf-… /bin/sh -c id
   💥 exit    5g-cp/open5gs-cp-amf-… /bin/sh -c id SIGKILL
   ```

4. El pod del AMF sigue `Running` y sin reinicios: muere el intruso, no el AMF.
   `make smoke` sigue dando `attach=SI`.

Eventos en crudo:

```bash
kubectl -n kube-system exec ds/tetragon -c tetragon -- \
  tetra getevents -o compact --namespace 5g-cp --pods <pod-del-amf>
```

### Observabilidad en las redes dedicadas (con `deploy_multus: true`)

```bash
kubectl -n kube-system exec ds/tetragon -c tetragon -- \
  tetra getevents -o compact --policy-names sockets-redes-dedicadas
make ran-restart          # provoca NG Setup y una sesión PDU nuevas
```

Deben aparecer el AMF haciendo `bind` en 10.10.0.10 (SCTP 38412), el UPF en
10.10.0.30:2152 y 10.10.6.30, y el gNB en 10.10.0.20, cada uno con su binario, su
pod y su contenedor. Cualquier otro proceso con una dirección de esas redes es una
anomalía. Hubble, en cambio, no muestra nada de esto (Fase 1).

## 4. Supuestos sin verificar

| Supuesto | Si falla |
|---|---|
| Existe el chart `cilium/tetragon` 1.1.2 | `helm` falla: cambia `tetragon_chart_version` |
| El entrypoint de Gradiant hace `exec` del binario del AMF y no lanza shells hijas | El AMF muere al arrancar con la política aplicada: `kubectl delete tracingpolicynamespaced -n 5g-cp amf-sin-shell`, mira los eventos y amplía la excepción |
| `matchPIDs` con `isNamespacePID: true` y el operador `Postfix` sobre `linux_binprm` en Tetragon 1.1 | La política no carga (`kubectl describe tracingpolicynamespaced …`) o no mata: probar con la lista de rutas exactas (`Equal`) |
| Una shell de `kubectl exec` no es el PID 1 del contenedor | Si lo fuera, la demo no la mataría: comprobar con `tetra getevents` el PID que reporta |
| El tipo `sockaddr` y el operador `SAddr` con CIDR en `security_socket_bind`/`connect` | La política de sockets no carga: dejar solo `bind`, o usar `tcp_connect` con el tipo `sock` y filtrar por `DAddr` |
| Las herramientas de la lista no las usa ningún proceso legítimo del AMF (sondas, scripts del chart) | Pod en CrashLoop o sondas fallando: mirar qué binario mata Tetragon y sacarlo de la lista o acotar más |

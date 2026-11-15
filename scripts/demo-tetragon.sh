#!/usr/bin/env bash
# demo-tetragon.sh — Fase 6: compromiso del AMF.
#
# Simula que alguien consigue ejecutar algo dentro del contenedor del AMF:
#   1) abrir una shell (kubectl exec ... sh -c 'id');
#   2) lanzar una herramienta de red (curl) contra el NRF.
# Con la TracingPolicyNamespaced amf-sin-shell, Tetragon mata ambos procesos
# en el kernel (Sigkill en security_bprm_check) antes de que se ejecuten:
# kubectl exec termina con código 137 y no sale ni un paquete.
# Luego muestra los eventos de Tetragon de ese pod.
#
# No modifica nada en el core. El AMF sigue funcionando (el que muere es el
# proceso intruso, no el AMF): el script lo comprueba al final.
#
# Uso: scripts/demo-tetragon.sh
set -uo pipefail
NS_CP="${NS_CP:-5g-cp}"
AMF="$(kubectl -n "$NS_CP" get pod -l app.kubernetes.io/name=amf -o jsonpath='{.items[0].metadata.name}')"
NODE="$(kubectl -n "$NS_CP" get pod "$AMF" -o jsonpath='{.spec.nodeName}')"
echo "AMF: ${NS_CP}/${AMF} (nodo ${NODE})"
kubectl get tracingpoliciesnamespaced -n "$NS_CP" 2>/dev/null || true

# Los eventos de Tetragon son por nodo y 'tetra getevents' solo muestra los que
# llegan mientras escucha: se abre el flujo en el pod de Tetragon del nodo del
# AMF ANTES de los intentos, y se cierra después. Se filtra por política, no por
# pod: en security_bprm_check el proceso aún es el runc del host que está
# lanzando el exec, sin pod asociado, así que --namespace/--pod no lo ven.
TG="$(kubectl -n kube-system get pod -l app.kubernetes.io/name=tetragon \
  --field-selector spec.nodeName="$NODE" -o name)"
EV="$(mktemp)"
timeout 30 kubectl -n kube-system exec "$TG" -c tetragon -- \
  tetra getevents -o json --policy-names amf-sin-shell >"$EV" 2>/dev/null &
EV_PID=$!
sleep 3

echo; echo "== 1) Shell dentro del AMF =="
kubectl -n "$NS_CP" exec "$AMF" -- sh -c 'id'; echo "código de salida: $? (137 = matado por SIGKILL)"

echo; echo "== 2) Herramienta de red dentro del AMF =="
kubectl -n "$NS_CP" exec "$AMF" -- curl -s -m 3 http://open5gs-cp-nrf-sbi:7777/ ; echo "código de salida: $?"

sleep 2
kill "$EV_PID" 2>/dev/null; wait "$EV_PID" 2>/dev/null
echo; echo "== Eventos de Tetragon del AMF (${TG#pod/}) =="
if [ -s "$EV" ]; then
  python3 - "$EV" <<'PY'
import json, sys
for line in open(sys.argv[1]):
    try:
        k = json.loads(line).get("process_kprobe")
    except ValueError:
        continue
    if not k:
        continue
    path = next((a["linux_binprm_arg"].get("path", "?") for a in k.get("args", [])
                 if "linux_binprm_arg" in a), "?")
    accion = k.get("action", "?").replace("KPROBE_ACTION_", "")
    print(f"💥 {accion:8} {path:22} {k.get('function_name', '?')} "
          f"(política {k.get('policy_name', '?')}, {k.get('process', {}).get('start_time', '')[:19]})")
PY
else echo "(sin eventos; ver docs/pruebas-fase6.md §3)"; fi
rm -f "$EV"

echo; echo "== El AMF sigue vivo =="
kubectl -n "$NS_CP" get pod "$AMF" -o custom-columns='POD:.metadata.name,ESTADO:.status.phase,REINICIOS:.status.containerStatuses[0].restartCount'

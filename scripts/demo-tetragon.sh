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
echo "AMF: ${NS_CP}/${AMF}"
kubectl get tracingpoliciesnamespaced -n "$NS_CP" 2>/dev/null || true

echo; echo "== 1) Shell dentro del AMF =="
kubectl -n "$NS_CP" exec "$AMF" -- sh -c 'id'; echo "código de salida: $? (137 = matado por SIGKILL)"

echo; echo "== 2) Herramienta de red dentro del AMF =="
kubectl -n "$NS_CP" exec "$AMF" -- curl -s -m 3 http://open5gs-cp-nrf-sbi:7777/ ; echo "código de salida: $?"

echo; echo "== Eventos de Tetragon del AMF =="
kubectl -n kube-system exec ds/tetragon -c tetragon -- \
  tetra getevents -o compact --namespace "$NS_CP" --pods "$AMF" --timeout 5s 2>/dev/null | tail -20 \
  || echo "(no se pudieron leer eventos; ver docs/pruebas-fase6.md §3)"

echo; echo "== El AMF sigue vivo =="
kubectl -n "$NS_CP" get pod "$AMF" -o custom-columns='POD:.metadata.name,ESTADO:.status.phase,REINICIOS:.status.containerStatuses[0].restartCount'

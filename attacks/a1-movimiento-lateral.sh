#!/bin/bash
# a1-movimiento-lateral.sh — A1: movimiento lateral desde la RAN hacia el core.
#
# Un pod comprometido en 5g-ran (attacker-ran, en el sitio de borde) intenta
# abrir conexión con cada servicio del plano de control y, si la SBI del NRF
# queda abierta, listar las NF registradas.
#
# Esperado con las políticas del lab: todos los intentos sin respuesta y, en
# Hubble, DROPPED por política (egress de 5g-ran e ingress de 5g-cp).
#
# Uso (desde node-master):
#   kubectl apply -f attacks/attacker-ran.yaml
#   bash attacks/a1-movimiento-lateral.sh
#   hubble observe -n 5g-ran --verdict DROPPED --last 20
set -uo pipefail
NS=5g-ran
POD=attacker-ran

echo "=== A1: movimiento lateral desde ${NS}/${POD} | $(date -u) ==="
kubectl -n "$NS" wait --for=condition=Ready "pod/${POD}" --timeout=120s >/dev/null

for target in \
  open5gs-cp-nrf-sbi:7777 open5gs-cp-scp-sbi:7777 open5gs-cp-amf-sbi:7777 \
  open5gs-cp-smf-sbi:7777 open5gs-cp-udm-sbi:7777 open5gs-cp-ausf-sbi:7777 \
  open5gs-cp-udr-sbi:7777 open5gs-cp-pcf-sbi:7777 open5gs-cp-mongodb:27017; do
  host="${target%%:*}.5g-cp.svc.cluster.local"
  port="${target##*:}"
  if kubectl -n "$NS" exec "$POD" -- nc -z -w2 "$host" "$port" >/dev/null 2>&1; then
    echo "ABIERTO   ${host}:${port}"
  else
    echo "cerrado   ${host}:${port}"
  fi
done

echo "--- Enumerar NF en el NRF ---"
kubectl -n "$NS" exec "$POD" -- curl -s --max-time 5 --http2-prior-knowledge \
  -o /dev/null -w "HTTP %{http_code}\n" \
  "http://open5gs-cp-nrf-sbi.5g-cp.svc.cluster.local:7777/nnrf-nfm/v1/nf-instances" \
  || echo "sin respuesta"

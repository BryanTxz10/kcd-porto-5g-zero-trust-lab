#!/usr/bin/env bash
# smoke-control-plane.sh — prueba de humo que ejercita el plano de control
# (SBI), no solo un ping del UE. Comprueba:
#   1) que el UE completa un registro 5G nuevo (Registration + PDU Session);
#   2) que una petición SBI legítima de discovery al NRF responde 2xx.
#
# La petición SBI sale del pod de prueba sbi-probe (5g-cp), no de dentro del
# AMF: en la Fase 6 Tetragon mata cualquier herramienta de red que se ejecute
# en el AMF. Si el pod monta un certificado (sbi_tls: true), la petición va
# por HTTPS con certificado de cliente; si no, en claro (HTTP/2 sin TLS).
#
# Uso: smoke-control-plane.sh [etiqueta]     (etiqueta libre para el log)
#      make smoke
set -uo pipefail
ETIQUETA="${1:-lab}"
NS_CP="${NS_CP:-5g-cp}"; NS_RAN="${NS_RAN:-5g-ran}"
NRF="${NRF_HOST:-open5gs-cp-nrf-sbi.${NS_CP}.svc.cluster.local}"
LOG="smoke_${ETIQUETA}.txt"
echo "=== SMOKE plano de control — ${ETIQUETA} | $(date -u) ===" | tee "$LOG"

# 1) Registro 5G nuevo: reinicia el UE y espera a uesimtun0
#    (implica Registration + autenticación + PDU Session por la SBI).
echo "--- Forzando re-registro del UE ---" | tee -a "$LOG"
kubectl -n "$NS_RAN" rollout restart deployment ueransim-ues >/dev/null 2>&1 || true
kubectl -n "$NS_RAN" rollout status deployment ueransim-ues --timeout=120s | tee -a "$LOG"
UE_POD="$(kubectl -n "$NS_RAN" get pod -l app.kubernetes.io/name=ueransim-ue \
  -o jsonpath='{.items[0].metadata.name}')"

t0=$(date +%s.%N); OK_TUN="NO"
for _ in $(seq 1 30); do
  if kubectl -n "$NS_RAN" exec "$UE_POD" -- ip -o a show uesimtun0 >/dev/null 2>&1; then
    OK_TUN="SI"; break
  fi
  sleep 2
done
t1=$(date +%s.%N)
ATTACH_S=$(awk "BEGIN{printf \"%.1f\", $t1-$t0}")
echo "attach_exitoso=${OK_TUN} tiempo_attach_s=${ATTACH_S}" | tee -a "$LOG"

# 2) SBI legítima (discovery de SMF pedido como AMF) desde sbi-probe.
PROBE_POD="$(kubectl -n "$NS_CP" get pod -l app.kubernetes.io/name=sbi-probe \
  -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)"
if [ -z "$PROBE_POD" ]; then
  echo "ERROR: no hay pod sbi-probe en ${NS_CP} (kubectl apply -f k8s/manifests/sbi-probe.yaml)" | tee -a "$LOG"
  exit 1
fi
RUTA="/nnrf-disc/v1/nf-instances?target-nf-type=SMF&requester-nf-type=AMF"
if kubectl -n "$NS_CP" exec "$PROBE_POD" -- test -s /etc/open5gs/tls/tls.crt 2>/dev/null; then
  MODO="mTLS"
  CODE=$(kubectl -n "$NS_CP" exec "$PROBE_POD" -- curl -s --http2 -o /dev/null -w '%{http_code}' \
    --cacert /etc/open5gs/tls/ca.crt --cert /etc/open5gs/tls/tls.crt --key /etc/open5gs/tls/tls.key \
    "https://${NRF}:7777${RUTA}")
else
  MODO="claro"
  CODE=$(kubectl -n "$NS_CP" exec "$PROBE_POD" -- curl -s --http2-prior-knowledge -o /dev/null \
    -w '%{http_code}' "http://${NRF}:7777${RUTA}")
fi
echo "sbi_modo=${MODO} sbi_discovery_http=${CODE}" | tee -a "$LOG"

echo "=== Resultado ${ETIQUETA}: attach=${OK_TUN} sbi(${MODO})=${CODE} ===" | tee -a "$LOG"
[ "$OK_TUN" = "SI" ] && [ "${CODE:0:1}" = "2" ]

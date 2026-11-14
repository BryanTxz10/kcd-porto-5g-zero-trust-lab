#!/usr/bin/env bash
# demo-l7-ciega.sh — Fase 4: la misma petición no autorizada al NRF, con la
# SBI en claro y con mTLS.
#
# Petición: GET /nnrf-nfm/v1/nf-instances desde sbi-probe, es decir, listar
# todos los perfiles de NF registrados. La política de Cilium solo deja a
# sbi-probe hacer GET /nnrf-disc/v1/nf-instances (discovery), así que:
#   - SBI en claro (overlay <modo>): el proxy L7 lee la ruta y responde 403.
#   - SBI con mTLS (overlay <modo>-tls): no hay reglas http (el proxy no puede
#     leer dentro del TLS); Cilium solo ve L3/L4 y la petición llega al NRF.
# No modifica nada en el core: es una lectura.
#
# El resultado exacto de cada caso hay que tomarlo del lab (Hubble), no de
# este comentario: docs/pruebas-fase4.md §4.
#
# Uso: bootstrap/checks/demo-l7-ciega.sh
set -uo pipefail
NS_CP="${NS_CP:-5g-cp}"
NRF="${NRF_HOST:-open5gs-cp-nrf-sbi.${NS_CP}.svc.cluster.local}"
RUTA="/nnrf-nfm/v1/nf-instances"
POD="$(kubectl -n "$NS_CP" get pod -l app.kubernetes.io/name=sbi-probe -o jsonpath='{.items[0].metadata.name}')"

echo "Políticas del lab aplicadas:"
kubectl get cnp -n "$NS_CP" -l kcd.io/policy-set=lab \
  -o custom-columns='NOMBRE:.metadata.name,MODO:.metadata.labels.kcd\.io/policy-mode,TLS:.metadata.labels.kcd\.io/sbi-tls'

if kubectl -n "$NS_CP" exec "$POD" -- test -s /etc/open5gs/tls/tls.crt 2>/dev/null; then
  echo; echo "== SBI con mTLS: GET ${RUTA} =="
  kubectl -n "$NS_CP" exec "$POD" -- curl -s --http2 -m 5 -o /dev/null \
    -w 'http_code=%{http_code}\n' \
    --cacert /etc/open5gs/tls/ca.crt --cert /etc/open5gs/tls/tls.crt --key /etc/open5gs/tls/tls.key \
    "https://${NRF}:7777${RUTA}"
else
  echo; echo "== SBI en claro: GET ${RUTA} =="
  kubectl -n "$NS_CP" exec "$POD" -- curl -s --http2-prior-knowledge -m 5 -o /dev/null \
    -w 'http_code=%{http_code}\n' "http://${NRF}:7777${RUTA}"
fi

echo
echo "Qué vio Cilium (últimos eventos de sbi-probe hacia el NRF):"
echo "  hubble observe --from-label app.kubernetes.io/name=sbi-probe --to-label app.kubernetes.io/name=nrf --last 10"
hubble observe --from-label app.kubernetes.io/name=sbi-probe \
  --to-label app.kubernetes.io/name=nrf --last 10 2>/dev/null || echo "(hubble CLI no disponible aquí)"

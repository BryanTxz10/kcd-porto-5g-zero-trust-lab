#!/usr/bin/env bash
# cold-start.sh — deja el 5G en servicio tras un arranque en frío o un
# reinicio del UPF, recreando los pods en el orden que el lab necesita.
#
# Por qué hace falta: al apagar, el daemon de Multus borra su 00-multus.conf.
# En el arranque siguiente los sandboxes que se crean antes de que el daemon
# lo reescriba salen solo con eth0: el AMF no puede enlazar su IP de N2 y el
# UPF se queda sin N3/N6. Recrear los pods con Multus ya listo lo corrige.
#
# Orden y esperas (cada una es una lección de la bitácora):
#   1. AMF y UPF        necesitan sus interfaces de Multus.
#   2. SMF              debe asociarse por PFCP con el UPF nuevo; se espera a
#                       que el pod viejo desaparezca antes de seguir.
#   3. gNB              "rollout status" no basta: se espera el NG Setup.
#   4. UE               nunca dos a la vez con el mismo IMSI.
#
# Uso: make cold-start        (o bash scripts/cold-start.sh)
set -euo pipefail

NS_CP="${NS_CP:-5g-cp}"
NS_UP="${NS_UP:-5g-up}"
NS_RAN="${NS_RAN:-5g-ran}"
PING_TARGET="${PING_TARGET:-8.8.8.8}"
MGMT_TARGET="${MGMT_TARGET:-192.168.100.10}"
T="${TIMEOUT:-300}"

say()  { printf '\n== %s\n' "$*"; }
fail() { printf '\nFALLO: %s\n' "$*" >&2; exit 1; }

# Borra los pods del Deployment y espera a que el viejo desaparezca y el
# nuevo esté listo. Con "rollout restart" conviven los dos unos segundos.
recreate() {
  local ns="$1" deploy="$2" sel
  sel="$(kubectl -n "$ns" get deploy "$deploy" \
    -o go-template='{{range $k,$v := .spec.selector.matchLabels}}{{$k}}={{$v}},{{end}}')"
  sel="${sel%,}"
  [ -n "$sel" ] || fail "no encuentro el selector de $ns/$deploy"
  kubectl -n "$ns" delete pod -l "$sel" --wait=true --timeout=120s
  kubectl -n "$ns" rollout status "deploy/$deploy" --timeout="${T}s"
}

# Espera hasta $3 segundos a que aparezca el patrón $4 en el log de $1/$2.
wait_log() {
  local ns="$1" deploy="$2" secs="$3" pattern="$4" i
  for ((i = 0; i < secs; i += 3)); do
    # grep -c lee todo el log: con -q cortaría la tubería y pipefail daría fallo.
    if kubectl -n "$ns" logs "deploy/$deploy" 2>/dev/null | grep -c -- "$pattern" >/dev/null; then
      return 0
    fi
    sleep 3
  done
  return 1
}

# El pod nuevo debe tener la red dedicada 'access' además de eth0.
has_access() {
  local ns="$1" deploy="$2" sel
  sel="$(kubectl -n "$ns" get deploy "$deploy" \
    -o go-template='{{range $k,$v := .spec.selector.matchLabels}}{{$k}}={{$v}},{{end}}')"
  kubectl -n "$ns" get pod -l "${sel%,}" \
    -o jsonpath='{.items[*].metadata.annotations.k8s\.v1\.cni\.cncf\.io/network-status}' \
    | grep -c '/access"' >/dev/null
}

MULTUS=false
if kubectl -n kube-system get ds kube-multus-ds >/dev/null 2>&1; then MULTUS=true; fi

say "Nodos"
kubectl wait --for=condition=Ready node --all --timeout="${T}s"

if $MULTUS; then
  say "Multus en todos los nodos"
  kubectl -n kube-system rollout status ds/kube-multus-ds --timeout="${T}s"
fi

say "DNS y admisión"
kubectl -n kube-system rollout status deploy/coredns --timeout="${T}s"
if kubectl get ns kyverno >/dev/null 2>&1; then
  kubectl -n kyverno rollout status deploy/kyverno-admission-controller --timeout="${T}s"
fi

say "AMF y UPF"
recreate "$NS_CP" open5gs-cp-amf
recreate "$NS_UP" open5gs-up-upf
if $MULTUS; then
  has_access "$NS_CP" open5gs-cp-amf || fail "el AMF no tiene la red access"
  has_access "$NS_UP" open5gs-up-upf || fail "el UPF no tiene la red access"
fi

say "SMF (un solo pod, asociado por PFCP al UPF)"
recreate "$NS_CP" open5gs-cp-smf
wait_log "$NS_CP" open5gs-cp-smf 60 "PFCP associated" \
  || fail "el SMF no se asoció por PFCP con el UPF"

say "gNB"
recreate "$NS_RAN" ueransim-gnb
wait_log "$NS_RAN" ueransim-gnb 90 "NG Setup procedure is successful" \
  || fail "el gNB no completó el NG Setup con el AMF"

# Sesión PDU y tráfico. Visto una vez: el UE obtiene uesimtun0 pero falla la
# autenticación NAS y no pasa tráfico; una sesión nueva lo resuelve.
ue_up() {
  local i
  recreate "$NS_RAN" ueransim-ues
  for ((i = 0; i < 90; i += 3)); do
    if kubectl -n "$NS_RAN" exec deploy/ueransim-ues -- ip -br a show uesimtun0 >/dev/null 2>&1; then
      break
    fi
    sleep 3
  done
  kubectl -n "$NS_RAN" exec deploy/ueransim-ues -- ip -br a show uesimtun0 || return 1
  kubectl -n "$NS_RAN" exec deploy/ueransim-ues -- ping -I uesimtun0 -c 3 -W 2 "$PING_TARGET"
}

say "UE: sesión PDU y datos hacia $PING_TARGET"
if ! ue_up; then
  say "UE: segundo intento"
  ue_up || fail "el UE no consigue sesión con tráfico; mira el log de ueransim-ues"
fi

if $MULTUS; then
  say "La red de gestión no es alcanzable desde el UE"
  if kubectl -n "$NS_RAN" exec deploy/ueransim-ues -- \
    ping -I uesimtun0 -c 2 -W 2 "$MGMT_TARGET" >/dev/null 2>&1; then
    fail "el UE llega a $MGMT_TARGET: revisa el firewall de dn-gw"
  fi
  echo "ok: $MGMT_TARGET bloqueada"
fi

say "5G en servicio"
kubectl get pods -A -o wide | grep -E 'upf|smf|amf|gnb|ues'

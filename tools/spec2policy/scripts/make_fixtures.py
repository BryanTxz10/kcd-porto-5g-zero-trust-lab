"""Genera los fixtures SINTÉTICOS de `hubble observe -o jsonpb` de fixtures/hubble/.

No son capturas reales: imitan el formato protojson de Hubble (Cilium 1.15) con
los labels del chart Gradiant de Open5GS en el namespace 5g-cp y el patrón de
comunicación indirecta vía SCP (Modelo D). Incluyen a propósito tres anomalías
para que el informe tenga algo que señalar. Determinista: misma salida siempre.

Uso: python scripts/make_fixtures.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from spec2policy import yamlio  # noqa: E402

OUT = HERE / "fixtures" / "hubble"
NS = "5g-cp"
NODE = "kind-worker"
T0 = datetime(2026, 11, 19, 9, 0, 0, tzinfo=timezone.utc)

# Direcciones y pods ficticios por NF (orden fijo).
NFS = ["nrf", "scp", "amf", "smf", "ausf", "udm", "udr", "pcf", "nssf", "bsf"]
IP = {nf: f"10.244.1.{10 + i}" for i, nf in enumerate(NFS)}
POD = {nf: f"open5gs-cp-{nf}-7d9f8c6b5-{'abcde'[i % 5]}{i}xq" for i, nf in enumerate(NFS)}
IDENTITY = {nf: 20000 + i for i, nf in enumerate(NFS)}

SUPI = "imsi-999700000000001"
NF_ID = "6f3e9c2a-1b7d-4e55-9a10-2c9b7f1d0e01"
SM_CTX = "3"
POL_ASSO = "1"


def labels(nf: str) -> list[str]:
    return [
        "k8s:app.kubernetes.io/instance=open5gs-cp",
        f"k8s:app.kubernetes.io/name={nf}",
        f"k8s:io.cilium.k8s.namespace.labels.kubernetes.io/metadata.name={NS}",
        "k8s:io.cilium.k8s.policy.cluster=default",
        f"k8s:io.cilium.k8s.policy.serviceaccount=open5gs-cp-{nf}",
        f"k8s:io.kubernetes.pod.namespace={NS}",
    ]


def endpoint(nf: str) -> dict:
    return {
        "ID": 100 + NFS.index(nf),
        "identity": IDENTITY[nf],
        "namespace": NS,
        "labels": labels(nf),
        "pod_name": POD[nf],
        "workloads": [{"name": f"open5gs-cp-{nf}", "kind": "Deployment"}],
    }


def impostor() -> tuple[dict, str]:
    """Pod sin label de NF (p. ej. un debug pod lanzado por un atacante)."""
    return (
        {
            "ID": 250,
            "identity": 31337,
            "namespace": NS,
            "labels": [
                f"k8s:io.cilium.k8s.namespace.labels.kubernetes.io/metadata.name={NS}",
                "k8s:io.cilium.k8s.policy.cluster=default",
                "k8s:io.cilium.k8s.policy.serviceaccount=default",
                f"k8s:io.kubernetes.pod.namespace={NS}",
                "k8s:run=netshoot",
            ],
            "pod_name": "netshoot",
        },
        "10.244.1.99",
    )


class Writer:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.t = T0

    def tick(self, ms: int = 137) -> str:
        self.t += timedelta(milliseconds=ms)
        return self.t.isoformat().replace("+00:00", "Z")

    def emit(self, flow: dict) -> None:
        time = self.tick()
        flow["time"] = time
        self.lines.append(
            json.dumps({"flow": flow, "node_name": NODE, "time": time}, ensure_ascii=False)
        )

    # --- tipos de evento ----------------------------------------------------------------
    def l7(
        self,
        src: str,
        dst: str,
        method: str,
        path: str,
        *,
        src_ep: dict | None = None,
        src_ip: str | None = None,
        status: int = 200,
        verdict: str = "FORWARDED",
    ) -> None:
        src_ep = src_ep or endpoint(src)
        src_ip = src_ip or IP[src]
        host = f"open5gs-cp-{dst}-sbi.{NS}.svc.cluster.local:7777"
        base = {
            "verdict": verdict,
            "IP": {"source": src_ip, "destination": IP[dst], "ipVersion": "IPv4"},
            "l4": {
                "TCP": {"source_port": 40000 + len(self.lines) % 20000, "destination_port": 7777}
            },
            "source": src_ep,
            "destination": endpoint(dst),
            "Type": "L7",
            "node_name": NODE,
            "event_type": {"type": 129},
            "traffic_direction": "INGRESS",
            "is_reply": False,
            "Summary": f"HTTP/2 {method} http://{host}{path}",
        }
        req = dict(base)
        req["l7"] = {
            "type": "REQUEST",
            "http": {
                "method": method,
                "url": f"http://{host}{path}",
                "protocol": "HTTP/2",
                "headers": [
                    {"key": "Accept", "value": "application/json,application/problem+json"},
                    {"key": "User-Agent", "value": f"{src.upper()}"},
                ],
            },
        }
        self.emit(req)
        if verdict == "DROPPED":
            return
        resp = dict(base)
        resp["is_reply"] = True
        resp["Summary"] = (
            f"HTTP/2 {status} {self.t.microsecond // 1000}ms ({method} http://{host}{path})"
        )
        resp["l7"] = {
            "type": "RESPONSE",
            "latency_ns": 1_200_000 + 1000 * (len(self.lines) % 97),
            "http": {
                "code": status,
                "method": method,
                "url": f"http://{host}{path}",
                "protocol": "HTTP/2",
                "headers": [{"key": "Content-Type", "value": "application/json"}],
            },
        }
        self.emit(resp)

    def l34(
        self, src: str, dst: str, port: int = 7777, *, verdict: str = "FORWARDED", flags=None
    ) -> None:
        flags = flags or {"SYN": True}
        self.emit(
            {
                "verdict": verdict,
                "IP": {"source": IP[src], "destination": IP[dst], "ipVersion": "IPv4"},
                "l4": {
                    "TCP": {
                        "source_port": 50000 + len(self.lines) % 10000,
                        "destination_port": port,
                        "flags": flags,
                    }
                },
                "source": endpoint(src),
                "destination": endpoint(dst),
                "Type": "L3_L4",
                "node_name": NODE,
                "event_type": {"type": 4, "sub_type": 3},
                "traffic_direction": "INGRESS",
                "is_reply": False,
                "Summary": "TCP Flags: SYN",
            }
        )


def sin_tls() -> list[str]:
    """Arranque del core + registro de un UE + sesión PDU, en claro, con proxy L7."""
    w = Writer()
    # 1) Registro y heartbeat en el NRF: DIRECTO, cada NF con su cliente NRF.
    for nf in ["scp", "amf", "smf", "ausf", "udm", "udr", "pcf", "nssf", "bsf"]:
        w.l7(
            nf,
            "nrf",
            "PUT",
            f"/nnrf-nfm/v1/nf-instances/{NF_ID[:-2]}{NFS.index(nf):02d}",
            status=201,
        )
    for nf in ["amf", "smf", "udm", "pcf"]:
        w.l7(
            nf,
            "nrf",
            "PATCH",
            f"/nnrf-nfm/v1/nf-instances/{NF_ID[:-2]}{NFS.index(nf):02d}",
            status=204,
        )
    w.l7("amf", "nrf", "POST", "/nnrf-nfm/v1/subscriptions", status=201)
    w.l7("scp", "nrf", "POST", "/nnrf-nfm/v1/subscriptions", status=201)
    # Notificación de estado del NRF a las NF suscritas (callback directo).
    w.l7("nrf", "amf", "POST", "/nnrf-nfm/v1/nf-status-notify", status=204)
    w.l7("nrf", "scp", "POST", "/nnrf-nfm/v1/nf-status-notify", status=204)

    # 2) Descubrimiento: con Modelo D, solo el SCP pregunta al NRF.
    w.l7(
        "scp", "nrf", "GET", "/nnrf-disc/v1/nf-instances?target-nf-type=AUSF&requester-nf-type=AMF"
    )
    w.l7(
        "scp", "nrf", "GET", "/nnrf-disc/v1/nf-instances?target-nf-type=UDM&requester-nf-type=AUSF"
    )
    w.l7("scp", "nrf", "GET", "/nnrf-disc/v1/nf-instances?target-nf-type=UDR&requester-nf-type=UDM")
    w.l7("scp", "nrf", "GET", "/nnrf-disc/v1/nf-instances?target-nf-type=PCF&requester-nf-type=AMF")
    w.l7("scp", "nrf", "GET", "/nnrf-disc/v1/nf-instances?target-nf-type=SMF&requester-nf-type=AMF")
    w.l7("scp", "nrf", "GET", "/nnrf-disc/v1/nf-instances?target-nf-type=BSF&requester-nf-type=PCF")

    # 3) Registro del UE: AMF -> SCP -> AUSF -> SCP -> UDM -> SCP -> UDR.
    w.l7("amf", "scp", "POST", "/nausf-auth/v1/ue-authentications", status=201)
    w.l7("scp", "ausf", "POST", "/nausf-auth/v1/ue-authentications", status=201)
    w.l7("ausf", "scp", "POST", f"/nudm-ueau/v1/{SUPI}/security-information/generate-auth-data")
    w.l7("scp", "udm", "POST", f"/nudm-ueau/v1/{SUPI}/security-information/generate-auth-data")
    w.l7(
        "udm",
        "scp",
        "GET",
        f"/nudr-dr/v2/subscription-data/{SUPI}/authentication-data/authentication-subscription",
    )
    w.l7(
        "scp",
        "udr",
        "GET",
        f"/nudr-dr/v2/subscription-data/{SUPI}/authentication-data/authentication-subscription",
    )
    w.l7("amf", "scp", "PUT", "/nausf-auth/v1/ue-authentications/1/5g-aka-confirmation")
    w.l7("scp", "ausf", "PUT", "/nausf-auth/v1/ue-authentications/1/5g-aka-confirmation")
    w.l7("ausf", "scp", "POST", f"/nudm-ueau/v1/{SUPI}/auth-events", status=201)
    w.l7("scp", "udm", "POST", f"/nudm-ueau/v1/{SUPI}/auth-events", status=201)
    w.l7(
        "udm",
        "scp",
        "PUT",
        f"/nudr-dr/v2/subscription-data/{SUPI}/authentication-data/authentication-status",
        status=204,
    )
    w.l7(
        "scp",
        "udr",
        "PUT",
        f"/nudr-dr/v2/subscription-data/{SUPI}/authentication-data/authentication-status",
        status=204,
    )
    # UECM + SDM
    w.l7("amf", "scp", "PUT", f"/nudm-uecm/v1/{SUPI}/registrations/amf-3gpp-access", status=201)
    w.l7("scp", "udm", "PUT", f"/nudm-uecm/v1/{SUPI}/registrations/amf-3gpp-access", status=201)
    w.l7(
        "udm",
        "scp",
        "PUT",
        f"/nudr-dr/v2/subscription-data/{SUPI}/context-data/amf-3gpp-access",
        status=204,
    )
    w.l7(
        "scp",
        "udr",
        "PUT",
        f"/nudr-dr/v2/subscription-data/{SUPI}/context-data/amf-3gpp-access",
        status=204,
    )
    w.l7(
        "amf",
        "scp",
        "GET",
        f"/nudm-sdm/v2/{SUPI}/am-data?plmn-id=%7B%22mcc%22%3A%22999%22%2C%22mnc%22%3A%2270%22%7D",
    )
    w.l7(
        "scp",
        "udm",
        "GET",
        f"/nudm-sdm/v2/{SUPI}/am-data?plmn-id=%7B%22mcc%22%3A%22999%22%2C%22mnc%22%3A%2270%22%7D",
    )
    w.l7(
        "udm", "scp", "GET", f"/nudr-dr/v2/subscription-data/{SUPI}/99970/provisioned-data/am-data"
    )
    w.l7(
        "scp", "udr", "GET", f"/nudr-dr/v2/subscription-data/{SUPI}/99970/provisioned-data/am-data"
    )
    w.l7("amf", "scp", "GET", f"/nudm-sdm/v2/{SUPI}/smf-select-data")
    w.l7("scp", "udm", "GET", f"/nudm-sdm/v2/{SUPI}/smf-select-data")
    w.l7("amf", "scp", "GET", f"/nudm-sdm/v2/{SUPI}/ue-context-in-smf-data")
    w.l7("scp", "udm", "GET", f"/nudm-sdm/v2/{SUPI}/ue-context-in-smf-data")
    w.l7("amf", "scp", "POST", f"/nudm-sdm/v2/{SUPI}/sdm-subscriptions", status=201)
    w.l7("scp", "udm", "POST", f"/nudm-sdm/v2/{SUPI}/sdm-subscriptions", status=201)
    # Política AM: AMF -> SCP -> PCF -> SCP -> UDR
    w.l7("amf", "scp", "POST", "/npcf-am-policy-control/v1/policies", status=201)
    w.l7("scp", "pcf", "POST", "/npcf-am-policy-control/v1/policies", status=201)
    w.l7("pcf", "scp", "GET", f"/nudr-dr/v2/policy-data/ues/{SUPI}/am-data")
    w.l7("scp", "udr", "GET", f"/nudr-dr/v2/policy-data/ues/{SUPI}/am-data")
    # Selección de slice
    w.l7(
        "amf",
        "scp",
        "GET",
        "/nnssf-nsselection/v2/network-slice-information?nf-type=AMF&nf-id=" + NF_ID,
    )
    w.l7(
        "scp",
        "nssf",
        "GET",
        "/nnssf-nsselection/v2/network-slice-information?nf-type=AMF&nf-id=" + NF_ID,
    )

    # 4) Sesión PDU: AMF -> SCP -> SMF; SMF -> SCP -> UDM/PCF; PCF -> SCP -> BSF/UDR.
    w.l7("amf", "scp", "POST", "/nsmf-pdusession/v1/sm-contexts", status=201)
    w.l7("scp", "smf", "POST", "/nsmf-pdusession/v1/sm-contexts", status=201)
    w.l7("smf", "scp", "PUT", f"/nudm-uecm/v1/{SUPI}/registrations/smf-registrations/1", status=201)
    w.l7("scp", "udm", "PUT", f"/nudm-uecm/v1/{SUPI}/registrations/smf-registrations/1", status=201)
    w.l7(
        "smf",
        "scp",
        "GET",
        f"/nudm-sdm/v2/{SUPI}/sm-data?single-nssai=%7B%22sst%22%3A1%7D&dnn=internet",
    )
    w.l7(
        "scp",
        "udm",
        "GET",
        f"/nudm-sdm/v2/{SUPI}/sm-data?single-nssai=%7B%22sst%22%3A1%7D&dnn=internet",
    )
    w.l7(
        "udm",
        "scp",
        "GET",
        f"/nudr-dr/v2/subscription-data/{SUPI}/99970/provisioned-data/sm-data?single-nssai=%7B%22sst%22%3A1%7D&dnn=internet",
    )
    w.l7(
        "scp",
        "udr",
        "GET",
        f"/nudr-dr/v2/subscription-data/{SUPI}/99970/provisioned-data/sm-data?single-nssai=%7B%22sst%22%3A1%7D&dnn=internet",
    )
    w.l7("smf", "scp", "POST", "/npcf-smpolicycontrol/v1/sm-policies", status=201)
    w.l7("scp", "pcf", "POST", "/npcf-smpolicycontrol/v1/sm-policies", status=201)
    w.l7("pcf", "scp", "POST", "/nbsf-management/v1/pcfBindings", status=201)
    w.l7("scp", "bsf", "POST", "/nbsf-management/v1/pcfBindings", status=201)
    w.l7("pcf", "scp", "GET", f"/nudr-dr/v2/policy-data/ues/{SUPI}/sm-data?dnn=internet")
    w.l7("scp", "udr", "GET", f"/nudr-dr/v2/policy-data/ues/{SUPI}/sm-data?dnn=internet")
    # SMF -> AMF: N1N2MessageTransfer (vía SCP)
    w.l7("smf", "scp", "POST", f"/namf-comm/v1/ue-contexts/{SUPI}/n1-n2-messages")
    w.l7("scp", "amf", "POST", f"/namf-comm/v1/ue-contexts/{SUPI}/n1-n2-messages")
    w.l7("amf", "scp", "POST", f"/nsmf-pdusession/v1/sm-contexts/{SM_CTX}/modify", status=204)
    w.l7("scp", "smf", "POST", f"/nsmf-pdusession/v1/sm-contexts/{SM_CTX}/modify", status=204)
    # Callback PCF -> SMF (directo en nuestro modelo, no verificado)
    w.l7("pcf", "smf", "POST", f"/nsmf-callback/v1/sm-policy-notify/{SM_CTX}", status=204)
    w.l7("pcf", "amf", "POST", f"/namf-callback/v1/am-policy-notify/{POL_ASSO}", status=204)

    # 5) Ruido L3/L4 (handshakes a 7777, MongoDB, métricas) y un drop.
    for nf in ["amf", "smf", "udm"]:
        w.l34(nf, "nrf")
    w.l34("udr", "udr", port=27017)
    w.l34("amf", "amf", port=9090)
    w.l34("amf", "udm", verdict="DROPPED")  # bloqueado por la política L3/L4 de c2

    # 6) ANOMALÍAS (sintéticas, para que el informe tenga hallazgos):
    #    a) pod sin identidad de NF lee el NRF (movimiento lateral desde un debug pod)
    imp, imp_ip = impostor()
    w.l7("netshoot", "nrf", "GET", "/nnrf-nfm/v1/nf-instances", src_ep=imp, src_ip=imp_ip)
    w.l7(
        "netshoot",
        "nrf",
        "GET",
        "/nnrf-disc/v1/nf-instances?target-nf-type=UDM&requester-nf-type=AMF",
        src_ep=imp,
        src_ip=imp_ip,
    )
    #    b) AMF habla DIRECTO con el UDM saltándose el SCP (consumidor legítimo, ruta ilegítima)
    w.l7("amf", "udm", "GET", f"/nudm-sdm/v2/{SUPI}/am-data")
    #    c) SMF (no consumidor de nudr-dr) modifica datos en el UDR: operación válida en
    #       la API, origen no autorizado. Solo se detecta en la entrada del SCP: el UDR
    #       lo ve llegar desde el SCP, como todo lo demás.
    ctx = f"/nudr-dr/v2/subscription-data/{SUPI}/context-data/amf-3gpp-access"
    w.l7("smf", "scp", "PATCH", ctx, status=204)
    w.l7("scp", "udr", "PATCH", ctx, status=204)
    #    d) un path que no existe en la API del UDM
    w.l7("scp", "udm", "GET", "/nudm-sdm/v2/admin/dump", status=404)
    return w.lines


def mtls_sin_l7() -> list[str]:
    """Mismo core con mTLS en la SBI: el proxy solo ve TCP; ninguna petición HTTP."""
    w = Writer()
    for src, dst in [
        ("amf", "nrf"),
        ("smf", "nrf"),
        ("udm", "nrf"),
        ("scp", "nrf"),
        ("amf", "scp"),
        ("scp", "ausf"),
        ("ausf", "scp"),
        ("scp", "udm"),
        ("udm", "scp"),
        ("scp", "udr"),
        ("amf", "scp"),
        ("scp", "pcf"),
        ("amf", "scp"),
        ("scp", "smf"),
        ("smf", "scp"),
        ("scp", "amf"),
    ]:
        w.l34(src, dst)
        w.l34(src, dst, flags={"ACK": True, "PSH": True})
    w.l34("udr", "udr", port=27017)
    return w.lines


def main() -> None:
    yamlio.write_text(OUT / "sbi-sin-tls.jsonl", "\n".join(sin_tls()) + "\n")
    yamlio.write_text(OUT / "sbi-mtls-sin-l7.jsonl", "\n".join(mtls_sin_l7()) + "\n")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()

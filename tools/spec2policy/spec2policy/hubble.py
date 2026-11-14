"""Parser de `hubble observe -o jsonpb` con foco en los requests HTTP (L7).

Formato: una línea JSON por evento. Hubble envuelve el flujo como
{"flow": {...}, "node_name": ..., "time": ...}; también se aceptan flujos sin
envoltorio. Los nombres de campo pueden venir en camelCase (protojson) o en
snake_case (jsonpb antiguo): se aceptan ambos.

Solo se extraen los eventos L7 de tipo REQUEST con bloque `http`. Las respuestas
y los flujos L3/L4 se cuentan en las estadísticas (sirven para detectar que hay
tráfico SBI sin visibilidad L7, p. ej. con mTLS activo).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

LABEL_PREFIX = "k8s:"
DEFAULT_NF_LABEL = "app.kubernetes.io/name"


@dataclass(frozen=True)
class HttpFlow:
    time: str
    verdict: str
    src_namespace: str
    src_pod: str
    src_nf: str | None
    dst_namespace: str
    dst_pod: str
    dst_nf: str | None
    dst_port: int | None
    method: str
    url: str
    path: str
    protocol: str = ""
    src_labels: tuple[str, ...] = ()
    dst_labels: tuple[str, ...] = ()

    @property
    def src_label(self) -> str:
        return self.src_nf or f"?({self.src_pod or self.src_namespace or 'desconocido'})"

    @property
    def dst_label(self) -> str:
        return self.dst_nf or f"?({self.dst_pod or self.dst_namespace or 'desconocido'})"


@dataclass
class ParseStats:
    lines: int = 0
    invalid_json: int = 0
    flows: int = 0
    l7_requests: int = 0
    l7_responses: int = 0
    l7_other: int = 0
    l34_sbi: int = 0  # TCP hacia el puerto SBI sin bloque L7
    l34_other: int = 0
    dropped: int = 0
    by_verdict: dict[str, int] = field(default_factory=dict)

    @property
    def l7_blind(self) -> bool:
        """Hay tráfico SBI pero ninguna petición HTTP visible: mTLS o sin proxy."""
        return self.l7_requests == 0 and self.l34_sbi > 0


@dataclass
class ParseResult:
    flows: list[HttpFlow]
    stats: ParseStats
    sources: list[str] = field(default_factory=list)


def _get(d: dict, *names, default=None):
    """Primer campo presente entre varias grafías (camelCase / snake_case)."""
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return default


def nf_from_labels(labels: Iterable[str], nf_label: str = DEFAULT_NF_LABEL) -> str | None:
    want = f"{LABEL_PREFIX}{nf_label}="
    for lab in labels:
        if lab.startswith(want):
            return lab[len(want) :]
        if lab.startswith(f"{nf_label}="):
            return lab.split("=", 1)[1]
    return None


def _endpoint(ep: dict | None, nf_label: str) -> tuple[str, str, str | None, tuple[str, ...]]:
    ep = ep or {}
    labels = tuple(str(x) for x in (_get(ep, "labels", default=[]) or []))
    ns = str(_get(ep, "namespace", default="") or "")
    pod = str(_get(ep, "pod_name", "podName", default="") or "")
    return ns, pod, nf_from_labels(labels, nf_label), labels


def _dst_port(flow: dict) -> int | None:
    l4 = _get(flow, "l4", "L4", default={}) or {}
    for proto in ("TCP", "tcp", "UDP", "udp", "SCTP", "sctp"):
        if proto in l4 and isinstance(l4[proto], dict):
            port = _get(l4[proto], "destination_port", "destinationPort")
            return int(port) if port is not None else None
    return None


def parse_flow(obj: dict, *, sbi_port: int, nf_label: str, stats: ParseStats) -> HttpFlow | None:
    flow = obj.get("flow", obj) if isinstance(obj, dict) else None
    if not isinstance(flow, dict):
        return None
    stats.flows += 1
    verdict = str(_get(flow, "verdict", default="") or "")
    stats.by_verdict[verdict] = stats.by_verdict.get(verdict, 0) + 1
    if verdict == "DROPPED":
        stats.dropped += 1
    dst_port = _dst_port(flow)
    l7 = _get(flow, "l7", "L7")
    if not isinstance(l7, dict):
        if dst_port == sbi_port:
            stats.l34_sbi += 1
        else:
            stats.l34_other += 1
        return None
    l7_type = str(_get(l7, "type", default="") or "").upper()
    http = _get(l7, "http", "HTTP")
    if l7_type == "RESPONSE":
        stats.l7_responses += 1
        return None
    if l7_type != "REQUEST" or not isinstance(http, dict):
        stats.l7_other += 1
        return None
    stats.l7_requests += 1
    url = str(_get(http, "url", default="") or "")
    parts = urlsplit(url) if url else None
    path = parts.path if parts else ""
    src_ns, src_pod, src_nf, src_labels = _endpoint(_get(flow, "source"), nf_label)
    dst_ns, dst_pod, dst_nf, dst_labels = _endpoint(_get(flow, "destination"), nf_label)
    return HttpFlow(
        time=str(_get(obj, "time", default=_get(flow, "time", default="")) or ""),
        verdict=verdict,
        src_namespace=src_ns,
        src_pod=src_pod,
        src_nf=src_nf,
        dst_namespace=dst_ns,
        dst_pod=dst_pod,
        dst_nf=dst_nf,
        dst_port=dst_port,
        method=str(_get(http, "method", default="") or "").upper(),
        url=url,
        path=path or "/",
        protocol=str(_get(http, "protocol", default="") or ""),
        src_labels=src_labels,
        dst_labels=dst_labels,
    )


def parse_lines(
    lines: Iterable[str], *, sbi_port: int = 7777, nf_label: str = DEFAULT_NF_LABEL
) -> ParseResult:
    stats = ParseStats()
    flows: list[HttpFlow] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        stats.lines += 1
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            stats.invalid_json += 1
            continue
        hf = parse_flow(obj, sbi_port=sbi_port, nf_label=nf_label, stats=stats)
        if hf is not None:
            flows.append(hf)
    return ParseResult(flows=flows, stats=stats)


def load_files(
    paths: Iterable[Path], *, sbi_port: int = 7777, nf_label: str = DEFAULT_NF_LABEL
) -> ParseResult:
    result = ParseResult(flows=[], stats=ParseStats())
    for p in paths:
        with Path(p).open(encoding="utf-8") as fh:
            part = parse_lines(fh, sbi_port=sbi_port, nf_label=nf_label)
        result.flows.extend(part.flows)
        result.sources.append(str(p))
        s, t = result.stats, part.stats
        for name in (
            "lines",
            "invalid_json",
            "flows",
            "l7_requests",
            "l7_responses",
            "l7_other",
            "l34_sbi",
            "l34_other",
            "dropped",
        ):
            setattr(s, name, getattr(s, name) + getattr(t, name))
        for k, v in t.by_verdict.items():
            s.by_verdict[k] = s.by_verdict.get(k, 0) + v
    return result

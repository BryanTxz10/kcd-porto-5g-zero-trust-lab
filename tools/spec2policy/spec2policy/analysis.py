"""Cruce estándar vs observado: filas por operación, hallazgos y radio de impacto."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from spec2policy.hubble import HttpFlow, ParseStats
from spec2policy.openapi import Operation, ServiceSpec, template_to_regex
from spec2policy.topology import ROUTE_SCP, Callback, Topology

ST_NO_OBSERVADO = "NO_OBSERVADO"
ST_CONFORME = "OBSERVADO_CONFORME"
ST_INESPERADO = "OBSERVADO_ORIGEN_INESPERADO"

UN_FUERA_ESTANDAR = "FUERA_DEL_ESTANDAR"
UN_DESTINO_DESCONOCIDO = "DESTINO_DESCONOCIDO"


@dataclass
class OpRow:
    """Una operación (método + path) tal y como la ve la entrada de la NF `at`."""

    at: str  # NF cuyo ingress describe la fila (productor, o el SCP)
    producer: str
    service: str
    spec: str
    method: str
    path_template: str
    operation_id: str
    consumers: list[str]
    route: str
    expected_sources: list[str]
    kind: str = "service"  # 'service' | 'callback'
    nota: str = ""
    observed: Counter = field(default_factory=Counter)

    @property
    def n_observed(self) -> int:
        return sum(self.observed.values())

    @property
    def unexpected_sources(self) -> list[str]:
        return sorted(s for s in self.observed if s not in self.expected_sources)

    @property
    def status(self) -> str:
        if self.n_observed == 0:
            return ST_NO_OBSERVADO
        return ST_INESPERADO if self.unexpected_sources else ST_CONFORME

    def path_regex(self, *, allow_query: bool = True) -> str:
        return template_to_regex(self.path_template, allow_query=allow_query)

    def matches(self, method: str, path: str) -> bool:
        if method.upper() != self.method:
            return False
        return (
            re.fullmatch(template_to_regex(self.path_template, allow_query=False), path) is not None
        )

    def explain_source(self, topo: Topology, src: str) -> str:
        """Por qué un origen es inesperado (para el informe)."""
        if src.startswith("?("):
            return "sin label de identidad de NF"
        if src in self.consumers and self.route == ROUTE_SCP and self.at == self.producer:
            return "consumidor legítimo pero directo, sin pasar por el SCP"
        if src not in topo.nfs:
            return "NF desconocida para la tabla"
        return "no es consumidor de este servicio según el estándar"


@dataclass
class Unmatched:
    flow: HttpFlow
    reason: str
    detail: str = ""


@dataclass
class BlastRow:
    consumer: str
    producers_std: list[str]
    ops_std: int
    ops_observed: int
    producers_observed: list[str]
    ops_scp_collapse: int  # lo que llega a los productores "como SCP"


@dataclass
class Analysis:
    rows: list[OpRow]
    unmatched: list[Unmatched]
    stats: ParseStats | None
    flow_sources: list[str]
    ignored_other_port: int = 0

    def rows_at(self, nf: str) -> list[OpRow]:
        return [r for r in self.rows if r.at == nf]

    def status_counts(self) -> Counter:
        return Counter(r.status for r in self.rows)


# --- construcción de filas ----------------------------------------------------


def _service_rows(topo: Topology, specs: dict[str, ServiceSpec]) -> list[OpRow]:
    rows: list[OpRow] = []
    for name, entry in topo.services.items():
        spec = specs.get(name)
        if spec is None:
            continue
        route = topo.route_of(name)
        for op in spec.operations:
            rows.append(_row_from_op(topo, entry.producer, entry.spec, entry.consumers, route, op))
            if route == ROUTE_SCP and topo.scp is not None:
                # La misma operación vista en la ENTRADA del SCP: aquí el origen
                # sí es el consumidor real.
                rows.append(
                    _row_from_op(
                        topo,
                        entry.producer,
                        entry.spec,
                        entry.consumers,
                        route,
                        op,
                        at=topo.scp.nf,
                        expected=sorted(entry.consumers),
                    )
                )
    return rows


def _row_from_op(
    topo: Topology,
    producer: str,
    spec: str,
    consumers: list[str],
    route: str,
    op: Operation,
    *,
    at: str | None = None,
    expected: list[str] | None = None,
) -> OpRow:
    return OpRow(
        at=at or producer,
        producer=producer,
        service=op.service,
        spec=spec,
        method=op.method,
        path_template=op.full_template,
        operation_id=op.operation_id,
        consumers=sorted(consumers),
        route=route,
        expected_sources=expected if expected is not None else topo.expected_sources(op.service),
    )


def _callback_rows(topo: Topology) -> list[OpRow]:
    rows: list[OpRow] = []
    for cb in topo.callbacks:
        for receiver in cb.receivers:
            rows.append(_callback_row(topo, cb, receiver))
    return rows


def _callback_row(topo: Topology, cb: Callback, receiver: str) -> OpRow:
    if cb.route == ROUTE_SCP and topo.scp is not None:
        expected = [topo.scp.nf]
    else:
        expected = [cb.notifier]
    return OpRow(
        at=receiver,
        producer=receiver,
        service=f"callback:{cb.name}",
        spec="callback",
        method=cb.method,
        path_template=cb.path,
        operation_id=cb.name,
        consumers=[cb.notifier],
        route=cb.route,
        expected_sources=expected,
        kind="callback",
        nota=cb.nota,
    )


def build_rows(topo: Topology, specs: dict[str, ServiceSpec]) -> list[OpRow]:
    return _service_rows(topo, specs) + _callback_rows(topo)


# --- cruce con lo observado ---------------------------------------------------


def analyze(
    topo: Topology,
    specs: dict[str, ServiceSpec],
    flows: list[HttpFlow] | None,
    stats: ParseStats | None = None,
    flow_sources: list[str] | None = None,
) -> Analysis:
    rows = build_rows(topo, specs)
    by_at: dict[str, list[OpRow]] = {}
    for r in rows:
        by_at.setdefault(r.at, []).append(r)
    unmatched: list[Unmatched] = []
    ignored = 0
    for f in flows or []:
        if f.dst_port is not None and f.dst_port != topo.sbi_port:
            ignored += 1
            continue
        if f.dst_nf is None or f.dst_nf not in topo.nfs:
            unmatched.append(Unmatched(f, UN_DESTINO_DESCONOCIDO, f"destino {f.dst_label}"))
            continue
        hit = next((r for r in by_at.get(f.dst_nf, []) if r.matches(f.method, f.path)), None)
        if hit is None:
            unmatched.append(
                Unmatched(
                    f, UN_FUERA_ESTANDAR, f"{f.method} {f.path} no está en la API de {f.dst_nf}"
                )
            )
            continue
        hit.observed[f.src_label] += 1
    return Analysis(
        rows=rows,
        unmatched=unmatched,
        stats=stats,
        flow_sources=list(flow_sources or []),
        ignored_other_port=ignored,
    )


# --- radio de impacto -----------------------------------------------------------


def blast_radius(topo: Topology, analysis: Analysis) -> list[BlastRow]:
    service_rows = [r for r in analysis.rows if r.kind == "service" and r.at == r.producer]
    ops_by_service: dict[str, int] = Counter(r.service for r in service_rows)
    scp_total = sum(n for s, n in ops_by_service.items() if topo.route_of(s) == ROUTE_SCP)
    out: list[BlastRow] = []
    for nf in sorted(topo.nfs):
        consumed = topo.services_consumed_by(nf)
        if not consumed:
            continue
        ops_std = sum(ops_by_service.get(s.name, 0) for s in consumed)
        producers_std = sorted({s.producer for s in consumed})
        observed_ops = 0
        producers_obs: set[str] = set()
        for r in analysis.rows:
            if r.kind != "service" or nf not in r.observed:
                continue
            # Evita contar dos veces lo visto en el productor y en el SCP.
            if r.route == ROUTE_SCP and r.at == r.producer:
                continue
            observed_ops += 1
            producers_obs.add(r.producer)
        via_scp = any(topo.route_of(s.name) == ROUTE_SCP for s in consumed)
        out.append(
            BlastRow(
                consumer=nf,
                producers_std=producers_std,
                ops_std=ops_std,
                ops_observed=observed_ops,
                producers_observed=sorted(producers_obs),
                ops_scp_collapse=scp_total if via_scp else 0,
            )
        )
    return out

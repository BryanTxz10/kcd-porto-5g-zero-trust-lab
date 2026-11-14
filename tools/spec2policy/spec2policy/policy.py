"""Generador de CiliumNetworkPolicy con reglas http por método y path.

Una política de ingress por NF (productores y SCP), con el mismo criterio de
selección que cilium-policies/c2 y c3: el par se identifica por namespace,
label de identidad (cib46-nf-type=core-nf) y nombre de NF (app.kubernetes.io/name).

Modos:
  standard  -> todo lo que el estándar permite a los consumidores de la tabla.
  observed  -> solo las operaciones del estándar que además se observaron desde
               el origen esperado (intersección: mínimo privilegio real).
"""

from __future__ import annotations

from dataclasses import dataclass

from spec2policy import yamlio
from spec2policy.analysis import ST_NO_OBSERVADO, Analysis, OpRow
from spec2policy.openapi import ServiceSpec
from spec2policy.topology import ROUTE_SCP, Topology

MODE_STANDARD = "standard"
MODE_OBSERVED = "observed"
MODES = (MODE_STANDARD, MODE_OBSERVED)

MANAGED_LABEL = "cib46.io/managed"


@dataclass
class PolicyOptions:
    mode: str = MODE_STANDARD
    allow_query: bool = True
    name_prefix: str = "spec2policy-sbi"
    managed_label: bool = True


def _rules_by_source(rows: list[OpRow], opts: PolicyOptions) -> dict[str, list[tuple[str, str]]]:
    """origen -> [(método, regex)] ordenado y sin duplicados."""
    out: dict[str, set[tuple[str, str]]] = {}
    for r in rows:
        if opts.mode == MODE_OBSERVED:
            sources = [s for s in r.expected_sources if s in r.observed]
        else:
            sources = list(r.expected_sources)
        for s in sources:
            out.setdefault(s, set()).add((r.method, r.path_regex(allow_query=opts.allow_query)))
    return {s: sorted(v) for s, v in sorted(out.items())}


def _header(topo: Topology, nf: str, specs: dict[str, ServiceSpec], opts: PolicyOptions) -> str:
    sources = sorted({s.source_label for s in specs.values()})
    lines = [
        f"# Generado por tools/spec2policy (modo {opts.mode}). NO EDITAR A MANO.",
        f"# Ingress SBI (TCP {topo.sbi_port}) de la NF '{nf}' en {topo.namespace}, derivado de:",
        f"#   - tabla productor/consumidor: {topo.source_path or 'services.yaml'}",
        "#   - OpenAPI 3GPP Rel-17 (extractos, mirror fijado por commit):",
    ]
    lines += [f"#       {s}" for s in sources]
    if topo.scp is not None and nf != topo.scp.nf:
        lines.append(
            "# SCP: en Open5GS las peticiones llegan al productor desde el SCP (comunicación"
        )
        lines.append(
            "# indirecta, TS 23.501 Anexo E). Por eso casi todo el ingress viene de 'scp'."
        )
    elif topo.scp is not None:
        lines.append("# SCP: aquí el origen es el consumidor real; esta es la política que de")
        lines.append("# verdad dice 'quién puede pedir qué' en una topología con SCP.")
    lines.append("# Estado: NO verificado en clúster (ver docs/pruebas-fase5.md).")
    return "\n".join(lines) + "\n"


def build_policy(
    topo: Topology, nf: str, rows: list[OpRow], specs: dict[str, ServiceSpec], opts: PolicyOptions
) -> tuple[str, dict] | None:
    rules = _rules_by_source(rows, opts)
    if not rules:
        return None
    ingress = []
    for src, pairs in rules.items():
        ingress.append(
            {
                "fromEndpoints": [{"matchLabels": topo.peer_selector(src)}],
                "toPorts": [
                    {
                        "ports": [{"port": str(topo.sbi_port), "protocol": "TCP"}],
                        "rules": {"http": [{"method": m, "path": p} for m, p in pairs]},
                    }
                ],
            }
        )
    services = sorted({r.service for r in rows if r.kind == "service"})
    metadata: dict = {
        "name": f"{opts.name_prefix}-{nf}",
        "namespace": topo.namespace,
        "labels": {"app.kubernetes.io/part-of": "spec2policy"},
        "annotations": {
            "description": (
                f"spec-as-policy ({opts.mode}): ingress SBI de {nf} con reglas HTTP por "
                f"método y path derivadas de los OpenAPI 3GPP de {', '.join(services)}."
            ),
            "spec2policy.cib46.io/mode": opts.mode,
            "spec2policy.cib46.io/services": ",".join(services),
        },
    }
    if opts.managed_label:
        # Mismo label que ponen los overlays Kustomize: 'make condition' las borra.
        metadata["labels"][MANAGED_LABEL] = "true"
    policy = {
        "apiVersion": "cilium.io/v2",
        "kind": "CiliumNetworkPolicy",
        "metadata": metadata,
        "spec": {
            "endpointSelector": {"matchLabels": topo.endpoint_selector(nf)},
            "ingress": ingress,
        },
    }
    return _header(topo, nf, specs, opts), policy


def build_all(
    topo: Topology, analysis: Analysis, specs: dict[str, ServiceSpec], opts: PolicyOptions
) -> dict[str, tuple[str, dict]]:
    """nombre de NF -> (cabecera comentada, CNP). Solo NF con alguna regla."""
    if opts.mode not in MODES:
        raise ValueError(f"modo desconocido: {opts.mode}")
    if opts.mode == MODE_OBSERVED and all(r.status == ST_NO_OBSERVADO for r in analysis.rows):
        raise ValueError("modo 'observed' sin flujos L7: no hay nada que generar")
    out: dict[str, tuple[str, dict]] = {}
    for nf in sorted({r.at for r in analysis.rows}):
        specs_nf = {
            r.service: specs[r.service]
            for r in analysis.rows_at(nf)
            if r.kind == "service" and r.service in specs
        }
        built = build_policy(topo, nf, analysis.rows_at(nf), specs_nf, opts)
        if built is not None:
            out[nf] = built
    return out


def render(header: str, policy: dict) -> str:
    return header + yamlio.dump(policy)


def build_visibility_policy(topo: Topology) -> tuple[str, dict]:
    """CNP de solo visibilidad L7: regla http vacía (todo permitido, todo parseado).

    Alternativa en Cilium 1.15 a la anotación policy.cilium.io/proxy-visibility
    (deprecada). Da a Hubble método y path de la SBI SIN restringir nada entre
    NF del core. Solo sirve en modo sin TLS: con mTLS el proxy no ve el HTTP.
    """
    header = (
        "# Generado por tools/spec2policy. Visibilidad L7 de la SBI para capturar flujos\n"
        "# con `hubble observe -o jsonpb` (método + path). Regla http vacía = permitir\n"
        f"# todo lo que llegue de {topo.namespace} al puerto {topo.sbi_port}, pero vía proxy.\n"
        "# No restringe tráfico entre NF; combínala con default-deny y el resto de capas.\n"
        "# Con mTLS activo (TS 33.501 §13.1) el proxy ve bytes cifrados: sin L7.\n"
        "# Estado: NO verificado en clúster.\n"
    )
    policy = {
        "apiVersion": "cilium.io/v2",
        "kind": "CiliumNetworkPolicy",
        "metadata": {
            "name": "spec2policy-sbi-l7-visibility",
            "namespace": topo.namespace,
            "labels": {"app.kubernetes.io/part-of": "spec2policy", MANAGED_LABEL: "true"},
            "annotations": {
                "description": (
                    "Visibilidad L7 de la SBI (sin restricción) para capturar método y path "
                    "con Hubble en modo sin TLS."
                )
            },
        },
        "spec": {
            "endpointSelector": {
                "matchExpressions": [
                    {"key": topo.label_nf_name, "operator": "In", "values": sorted(topo.nfs)}
                ]
            },
            "ingress": [
                {
                    "fromEndpoints": [{"matchLabels": {topo.label_namespace: topo.namespace}}],
                    "toPorts": [
                        {
                            "ports": [{"port": str(topo.sbi_port), "protocol": "TCP"}],
                            "rules": {"http": [{}]},
                        }
                    ],
                }
            ],
        },
    }
    return header, policy


def scp_note(topo: Topology) -> str:
    if topo.scp is None:
        return "Sin SCP: las peticiones llegan al productor desde el consumidor real."
    direct = ", ".join(topo.scp.direct_services) or "ninguno"
    return (
        f"Con SCP (modelo {topo.scp.model}), el productor ve como origen al SCP para todos los "
        f"servicios salvo: {direct}. La autorización por consumidor solo es posible en la "
        f"entrada del SCP."
    )


def route_label(route: str) -> str:
    return "vía SCP" if route == ROUTE_SCP else "directo"

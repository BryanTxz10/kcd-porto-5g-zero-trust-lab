"""Informe «blast radius map»: Markdown + CSV con estándar vs observado vs diferencia."""

from __future__ import annotations

import csv
import io
from collections import Counter

from spec2policy.analysis import (
    ST_CONFORME,
    ST_INESPERADO,
    ST_NO_OBSERVADO,
    UN_FUERA_ESTANDAR,
    Analysis,
    OpRow,
    blast_radius,
)
from spec2policy.openapi import ServiceSpec
from spec2policy.policy import route_label, scp_note
from spec2policy.topology import ROUTE_SCP, Topology

CSV_COLUMNS = [
    "punto_de_entrada",
    "productor",
    "servicio",
    "spec",
    "metodo",
    "path",
    "operation_id",
    "consumidores_estandar",
    "ruta",
    "origen_esperado",
    "observado_desde",
    "n_observado",
    "estado",
    "nota",
]

MTLS_WARNING = (
    "> ⚠️ **Sin visibilidad L7.** Hay tráfico TCP hacia el puerto SBI pero ninguna petición "
    "HTTP visible. Es lo que ocurre con mTLS activo en la SBI (TS 33.501 §13.1): el proxy de "
    "Cilium solo ve bytes cifrados y la política por método/path no puede evaluarse ni "
    "observarse. Captura en modo sin TLS (o termina TLS en un punto que el CNI vea) para "
    "obtener método y path. Este informe solo puede listar lo que el estándar permite."
)


def _join(items) -> str:
    return ";".join(str(i) for i in items)


def _observed_str(row: OpRow) -> str:
    return ";".join(f"{src}:{n}" for src, n in sorted(row.observed.items()))


def to_csv(analysis: Analysis) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLUMNS)
    for r in sorted(analysis.rows, key=_row_key):
        w.writerow(
            [
                r.at,
                r.producer,
                r.service,
                r.spec,
                r.method,
                r.path_template,
                r.operation_id,
                _join(r.consumers),
                r.route,
                _join(r.expected_sources),
                _observed_str(r),
                r.n_observed,
                r.status,
                r.nota,
            ]
        )
    for u in analysis.unmatched:
        f = u.flow
        w.writerow(
            [
                f.dst_label,
                f.dst_label,
                "",
                "",
                f.method,
                f.path,
                "",
                "",
                "",
                "",
                f"{f.src_label}:1",
                1,
                u.reason,
                u.detail,
            ]
        )
    return buf.getvalue()


def _row_key(r: OpRow):
    return (r.at, r.kind, r.service, r.path_template, r.method)


def _table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |" for row in rows]
    return "\n".join(out)


def _code(s: str) -> str:
    return f"`{s}`" if s else ""


def to_markdown(topo: Topology, analysis: Analysis, specs: dict[str, ServiceSpec]) -> str:
    stats = analysis.stats
    counts = analysis.status_counts()
    md: list[str] = []
    md.append("# Blast radius map — SBI del core 5G (spec-as-policy)")
    md.append("")
    md.append(
        "Cruce entre lo que el estándar 3GPP permite en la SBI (OpenAPI Rel-17 + tabla "
        "productor/consumidor de TS 23.501 §7.2), lo observado con Hubble (L7) y la diferencia. "
        "Generado por `tools/spec2policy`; no editar a mano."
    )
    md.append("")

    # --- fuentes ---------------------------------------------------------------
    md.append("## Fuentes")
    md.append("")
    md.append(f"- Tabla productor/consumidor: `{topo.source_path or 'services.yaml'}`")
    md.append("- OpenAPI 3GPP (extractos, mirror fijado por commit):")
    for s in sorted(specs.values(), key=lambda x: x.name):
        md.append(
            f"  - `{s.name}` {s.title} {s.version} — `{s.source_label}` ({len(s.operations)} op.)"
        )
    if analysis.flow_sources:
        md.append("- Flujos Hubble (`hubble observe -o jsonpb`):")
        md += [f"  - `{p}`" for p in analysis.flow_sources]
    else:
        md.append("- Flujos Hubble: **ninguno** (solo columna «estándar»).")
    md.append("")

    # --- estadísticas de captura ---------------------------------------------------
    if stats is not None:
        md.append("## Captura")
        md.append("")
        md.append(
            _table(
                ["Métrica", "Valor"],
                [
                    ["Líneas leídas", stats.lines],
                    ["JSON inválido", stats.invalid_json],
                    ["Flujos", stats.flows],
                    ["Peticiones HTTP (L7 REQUEST)", stats.l7_requests],
                    ["Respuestas HTTP (L7 RESPONSE)", stats.l7_responses],
                    [f"Flujos L3/L4 hacia TCP {topo.sbi_port} sin L7", stats.l34_sbi],
                    ["Flujos L3/L4 a otros puertos", stats.l34_other],
                    ["DROPPED", stats.dropped],
                    ["Peticiones L7 a otros puertos (ignoradas)", analysis.ignored_other_port],
                ],
            )
        )
        md.append("")
        if stats.l7_blind:
            md.append(MTLS_WARNING)
            md.append("")
        elif stats.l7_requests and stats.l34_sbi > stats.l7_requests * 5:
            md.append(
                "> ℹ️ Muchos más flujos L3/L4 al puerto SBI que peticiones HTTP: parte del "
                "tráfico no pasa por el proxy L7 (NF sin regla http o conexiones cifradas)."
            )
            md.append("")

    # --- SCP -----------------------------------------------------------------------
    md.append("## Efecto del SCP (comunicación indirecta)")
    md.append("")
    md.append(scp_note(topo))
    md.append("")
    md.append(
        "Por eso cada operación aparece dos veces en el detalle cuando va vía SCP: en la "
        "entrada del **productor** (origen esperado: `scp`) y en la entrada del **SCP** "
        "(origen esperado: los consumidores reales). La política por consumidor se decide en "
        "la segunda."
    )
    md.append("")

    # --- resumen -------------------------------------------------------------------
    md.append("## Resumen")
    md.append("")
    service_rows = [r for r in analysis.rows if r.kind == "service" and r.at == r.producer]
    md.append(
        _table(
            ["Indicador", "Valor"],
            [
                ["Servicios del estándar modelados", len(specs)],
                ["Operaciones (método+path) permitidas por el estándar", len(service_rows)],
                ["Callbacks modelados", len([r for r in analysis.rows if r.kind == "callback"])],
                ["Filas de política (productor + SCP)", len(analysis.rows)],
                [f"{ST_CONFORME}", counts.get(ST_CONFORME, 0)],
                [f"{ST_INESPERADO}", counts.get(ST_INESPERADO, 0)],
                [f"{ST_NO_OBSERVADO}", counts.get(ST_NO_OBSERVADO, 0)],
                [
                    f"{UN_FUERA_ESTANDAR} (peticiones sin operación en la API)",
                    len(analysis.unmatched),
                ],
            ],
        )
    )
    md.append("")

    # --- por productor ------------------------------------------------------------------
    md.append("## Por punto de entrada (ingress de cada NF)")
    md.append("")
    rows_tbl = []
    for nf in sorted({r.at for r in analysis.rows}):
        rs = analysis.rows_at(nf)
        c = Counter(r.status for r in rs)
        srcs = sorted({s for r in rs for s in r.expected_sources})
        obs = sorted({s for r in rs for s in r.observed})
        rows_tbl.append(
            [
                _code(nf),
                len(rs),
                ", ".join(_code(s) for s in srcs),
                ", ".join(_code(s) for s in obs) or "—",
                c.get(ST_CONFORME, 0),
                c.get(ST_INESPERADO, 0),
                c.get(ST_NO_OBSERVADO, 0),
            ]
        )
    md.append(
        _table(
            [
                "NF",
                "Op. permitidas",
                "Orígenes según estándar",
                "Orígenes observados",
                "Conformes",
                "Origen inesperado",
                "No observadas",
            ],
            rows_tbl,
        )
    )
    md.append("")

    # --- blast radius por consumidor ---------------------------------------------------
    md.append("## Radio de impacto por consumidor comprometido")
    md.append("")
    md.append(
        "Si un atacante toma el pod de la NF *consumidor*, ¿a cuántas operaciones de qué "
        "productores le da acceso la política? «Estándar» = política derivada del OpenAPI "
        "aplicada en la entrada del SCP. «Observado» = lo que realmente se vio hacer a esa NF. "
        "«Colapso SCP» = lo que el productor permite desde `scp`, es decir, lo que ese atacante "
        "alcanza si el SCP reenvía sin autorización propia (todo lo que el SCP puede pedir a "
        "cualquier productor)."
    )
    md.append("")
    br = blast_radius(topo, analysis)
    md.append(
        _table(
            [
                "Consumidor",
                "Productores (estándar)",
                "Op. estándar",
                "Op. observadas",
                "Productores observados",
                "Op. alcanzables tras colapso SCP",
            ],
            [
                [
                    _code(b.consumer),
                    ", ".join(_code(p) for p in b.producers_std),
                    b.ops_std,
                    b.ops_observed,
                    ", ".join(_code(p) for p in b.producers_observed) or "—",
                    b.ops_scp_collapse,
                ]
                for b in br
            ],
        )
    )
    md.append("")

    # --- hallazgos ------------------------------------------------------------------
    md.append("## Hallazgos (diferencia)")
    md.append("")
    findings = [r for r in analysis.rows if r.status == ST_INESPERADO]
    if not findings and not analysis.unmatched:
        md.append(
            "Sin desviaciones: todo lo observado está en el estándar y viene del origen esperado."
        )
    if findings:
        md.append("### Observado desde un origen inesperado")
        md.append("")
        md.append(
            _table(
                ["Entrada", "Método", "Path", "Origen esperado", "Visto desde", "Motivo"],
                [
                    [
                        _code(r.at),
                        r.method,
                        _code(r.path_template),
                        ", ".join(_code(s) for s in r.expected_sources),
                        ", ".join(f"{_code(s)}×{r.observed[s]}" for s in r.unexpected_sources),
                        "; ".join(r.explain_source(topo, s) for s in r.unexpected_sources),
                    ]
                    for r in sorted(findings, key=_row_key)
                ],
            )
        )
        md.append("")
    if analysis.unmatched:
        md.append("### Peticiones fuera del estándar o a destino desconocido")
        md.append("")
        md.append(
            _table(
                ["Destino", "Método", "Path", "Origen", "Tipo", "Detalle"],
                [
                    [
                        _code(u.flow.dst_label),
                        u.flow.method,
                        _code(u.flow.path),
                        _code(u.flow.src_label),
                        u.reason,
                        u.detail,
                    ]
                    for u in analysis.unmatched
                ],
            )
        )
        md.append("")

    # --- detalle (solo lo observado; el CSV lleva todo) --------------------------------------
    md.append("## Detalle de lo observado")
    md.append("")
    md.append("La tabla completa (incluidas las operaciones no observadas) está en el CSV.")
    md.append("")
    observed = [r for r in analysis.rows if r.n_observed]
    if observed:
        md.append(
            _table(
                ["Entrada", "Servicio", "Método", "Path", "Ruta", "Visto desde", "Estado"],
                [
                    [
                        _code(r.at),
                        _code(r.service),
                        r.method,
                        _code(r.path_template),
                        route_label(r.route),
                        ", ".join(f"{_code(s)}×{n}" for s, n in sorted(r.observed.items())),
                        r.status,
                    ]
                    for r in sorted(observed, key=_row_key)
                ],
            )
        )
    else:
        md.append("_Nada observado en L7._")
    md.append("")

    md.append("## Limitaciones")
    md.append("")
    md.append(
        "- Los consumidores de la tabla se limitan a las NF del testbed; el estándar permite "
        "más (NEF, SMSF, LMF, CHF…)."
    )
    md.append(
        "- Las rutas de callback y su paso por el SCP están marcadas como no verificadas en "
        "`services.yaml`."
    )
    md.append(
        f"- Solo se cruzan peticiones a TCP {topo.sbi_port}; los paths se comparan sin query "
        "string."
    )
    md.append(
        "- Con mTLS en la SBI no hay visibilidad L7: observar siempre en modo sin TLS (ver "
        "`docs/pruebas-fase5.md`)."
    )
    md.append("")
    return "\n".join(md)


def via_scp_rows(analysis: Analysis) -> list[OpRow]:
    return [r for r in analysis.rows if r.route == ROUTE_SCP]

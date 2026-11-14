"""CLI: `python -m spec2policy <subcomando>`.

Subcomandos:
  generate       CNP (una por NF) + informe MD/CSV a partir de OpenAPI, tabla y flujos.
  visibility     CNP de visibilidad L7 (regla http vacía) para capturar flujos sin TLS.
  inspect-flows  Resume un fichero jsonpb de Hubble: peticiones por origen→destino.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

from spec2policy import __version__, yamlio
from spec2policy.analysis import analyze
from spec2policy.hubble import load_files
from spec2policy.openapi import ServiceSpec, load_service
from spec2policy.policy import (
    MODE_STANDARD,
    MODES,
    PolicyOptions,
    build_all,
    build_visibility_policy,
    render,
)
from spec2policy.report import to_csv, to_markdown
from spec2policy.topology import Topology, load_topology

HERE = Path(__file__).resolve().parent.parent
DEFAULT_OPENAPI = HERE / "data" / "openapi"
DEFAULT_SERVICES = HERE / "data" / "services.yaml"


def load_specs(topo: Topology, openapi_dir: Path) -> dict[str, ServiceSpec]:
    specs: dict[str, ServiceSpec] = {}
    missing: list[str] = []
    for name, entry in topo.services.items():
        if not entry.openapi:
            missing.append(f"{name}: sin campo 'openapi'")
            continue
        path = openapi_dir / entry.openapi
        if not path.exists():
            missing.append(f"{name}: no existe {path}")
            continue
        specs[name] = load_service(path, service_name=name)
    if missing:
        raise SystemExit("OpenAPI no disponible:\n  - " + "\n  - ".join(missing))
    return specs


def display_path(path: Path) -> str:
    """Ruta relativa al cwd (POSIX) si es posible; así la salida no depende de la máquina."""
    try:
        return Path(os.path.relpath(path)).as_posix()
    except ValueError:  # otra unidad en Windows
        return Path(path).as_posix()


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--openapi-dir", type=Path, default=DEFAULT_OPENAPI, help="dir de extractos")
    p.add_argument("--services", type=Path, default=DEFAULT_SERVICES, help="tabla services.yaml")


def cmd_generate(args: argparse.Namespace) -> int:
    topo = load_topology(args.services)
    topo.source_path = display_path(args.services)
    specs = load_specs(topo, args.openapi_dir)
    flows = stats = None
    sources: list[str] = []
    if args.flows:
        parsed = load_files(args.flows, sbi_port=topo.sbi_port, nf_label=topo.label_nf_name)
        flows, stats = parsed.flows, parsed.stats
        sources = [display_path(Path(p)) for p in parsed.sources]
    analysis = analyze(topo, specs, flows, stats, sources)
    opts = PolicyOptions(mode=args.mode, allow_query=not args.no_query_suffix)
    policies = build_all(topo, analysis, specs, opts)

    out: Path = args.out
    cnp_dir = out / "cnp"
    cnp_dir.mkdir(parents=True, exist_ok=True)
    if args.clean:
        for old in cnp_dir.glob("*.yaml"):
            old.unlink()
    written: list[Path] = []
    for nf, (header, policy) in policies.items():
        path = cnp_dir / f"{opts.name_prefix}-{nf}.yaml"
        yamlio.write_text(path, render(header, policy))
        written.append(path)
    header, vis = build_visibility_policy(topo)
    vis_path = cnp_dir / "spec2policy-sbi-l7-visibility.yaml"
    yamlio.write_text(vis_path, render(header, vis))
    written.append(vis_path)
    md_path = out / "blast-radius-map.md"
    csv_path = out / "blast-radius-map.csv"
    yamlio.write_text(md_path, to_markdown(topo, analysis, specs))
    yamlio.write_text(csv_path, to_csv(analysis))
    written += [md_path, csv_path]

    counts = analysis.status_counts()
    print(f"spec2policy {__version__} · modo {opts.mode}")
    print(f"  servicios: {len(specs)} · filas: {len(analysis.rows)} · CNP: {len(policies)}")
    if stats is not None:
        print(
            f"  flujos: {stats.flows} · peticiones L7: {stats.l7_requests} · "
            f"L3/L4 a SBI sin L7: {stats.l34_sbi}"
        )
        if stats.l7_blind:
            print("  AVISO: tráfico SBI sin visibilidad L7 (¿mTLS activo?). Ver informe.")
    print("  estados: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if analysis.unmatched:
        print(f"  fuera del estándar / destino desconocido: {len(analysis.unmatched)}")
    for p in written:
        print(f"  -> {p.as_posix()}")
    return 0


def cmd_visibility(args: argparse.Namespace) -> int:
    topo = load_topology(args.services)
    header, policy = build_visibility_policy(topo)
    text = render(header, policy)
    if args.out:
        yamlio.write_text(args.out, text)
        print(f"-> {Path(args.out).as_posix()}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    nf_label = "app.kubernetes.io/name"
    sbi_port = args.sbi_port
    if args.services and Path(args.services).exists():
        topo = load_topology(args.services)
        nf_label, sbi_port = topo.label_nf_name, topo.sbi_port
    parsed = load_files(args.flows, sbi_port=sbi_port, nf_label=nf_label)
    s = parsed.stats
    print(
        f"flujos={s.flows} l7_req={s.l7_requests} l7_resp={s.l7_responses} "
        f"l34_sbi={s.l34_sbi} l34_otros={s.l34_other} dropped={s.dropped}"
    )
    if s.l7_blind:
        print("AVISO: hay tráfico SBI pero ninguna petición HTTP visible (¿mTLS activo?).")
    pairs = Counter((f.src_label, f.dst_label, f.method, f.path) for f in parsed.flows)
    for (src, dst, method, path), n in sorted(pairs.items()):
        print(f"{n:5d}  {src:>12} -> {dst:<6} {method:6} {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="spec2policy", description=__doc__.split("\n\n")[0])
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="genera CNP + informe")
    _common(g)
    g.add_argument(
        "--flows", type=Path, action="append", default=[], help="jsonpb de Hubble (repetible)"
    )
    g.add_argument("--mode", choices=MODES, default=MODE_STANDARD)
    g.add_argument("--out", type=Path, required=True, help="directorio de salida")
    g.add_argument(
        "--no-query-suffix",
        action="store_true",
        help="no añadir '(\\?.*)?' a los regex de path",
    )
    g.add_argument("--clean", action="store_true", help="borra los .yaml previos de out/cnp")
    g.set_defaults(func=cmd_generate)

    v = sub.add_parser("visibility", help="CNP de visibilidad L7 (sin restricción)")
    v.add_argument("--services", type=Path, default=DEFAULT_SERVICES)
    v.add_argument("--out", type=Path, default=None)
    v.set_defaults(func=cmd_visibility)

    i = sub.add_parser("inspect-flows", help="resume un jsonpb de Hubble")
    i.add_argument("flows", type=Path, nargs="+")
    i.add_argument("--services", type=Path, default=DEFAULT_SERVICES)
    i.add_argument("--sbi-port", type=int, default=7777)
    i.set_defaults(func=cmd_inspect)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))

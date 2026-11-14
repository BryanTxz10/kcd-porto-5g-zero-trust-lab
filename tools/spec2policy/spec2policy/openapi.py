"""Carga de OpenAPI 3GPP (Stage 3, TS 29.5xx) y conversión de paths a regex.

Trabaja con los extractos de data/openapi/ (o con los ficheros completos del
mirror jdegre/5GC_APIs, que tienen la misma estructura `servers` + `paths`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from spec2policy import yamlio

HTTP_METHODS = ("get", "put", "post", "delete", "patch", "head", "options")

_PARAM = re.compile(r"\{[^{}/]+\}")
_REGEX_SPECIAL = set(".^$*+?()[]{}|\\")


def escape_literal(text: str) -> str:
    """Escapa solo los metacaracteres de regex; deja '-' y '/' legibles (RE2/Envoy)."""
    return "".join("\\" + c if c in _REGEX_SPECIAL else c for c in text)


def base_path_from_servers(servers: list[dict] | None) -> str:
    """'{apiRoot}/nnrf-nfm/v1' -> '/nnrf-nfm/v1' (TS 29.501 §4.4: apiRoot + apiName + version)."""
    if not servers:
        raise ValueError("el OpenAPI no declara 'servers'; no se puede derivar el apiName")
    url = str(servers[0].get("url", ""))
    url = url.replace("{apiRoot}", "")
    if not url.startswith("/"):
        url = "/" + url
    return url.rstrip("/")


def template_to_regex(template: str, *, allow_query: bool = True) -> str:
    """Convierte '/a/{id}/b' en una regex para CiliumNetworkPolicy (rules.http.path).

    Cilium/Envoy evalúan el path como regex de coincidencia completa, así que no
    hace falta anclar. Los parámetros de ruta pasan a '[^/]+' (nunca cruzan '/').
    Con allow_query se admite una query string opcional ('(\\?.*)?'), porque el
    pseudo-header :path de HTTP/2 la incluye (p. ej. nnrf-disc usa ?target-nf-type=).
    """
    parts: list[str] = []
    pos = 0
    for m in _PARAM.finditer(template):
        parts.append(escape_literal(template[pos : m.start()]))
        parts.append("[^/?]+" if allow_query else "[^/]+")
        pos = m.end()
    parts.append(escape_literal(template[pos:]))
    regex = "".join(parts)
    if allow_query:
        regex += r"(\?.*)?"
    return regex


@dataclass(frozen=True)
class Operation:
    service: str
    base_path: str
    method: str
    path_template: str
    operation_id: str = ""
    summary: str = ""

    @property
    def full_template(self) -> str:
        return self.base_path + self.path_template

    def path_regex(self, *, allow_query: bool = True) -> str:
        return template_to_regex(self.full_template, allow_query=allow_query)

    def matches(self, method: str, path: str) -> bool:
        """¿Un request observado (método + path sin query) es esta operación?"""
        if method.upper() != self.method:
            return False
        return (
            re.fullmatch(template_to_regex(self.full_template, allow_query=False), path) is not None
        )


@dataclass
class ServiceSpec:
    name: str
    title: str
    version: str
    base_path: str
    operations: list[Operation] = field(default_factory=list)
    source: dict = field(default_factory=dict)

    @property
    def source_label(self) -> str:
        src = self.source
        if src.get("source") and src.get("commit"):
            return f"{src['source']}@{src['commit'][:12]}:{src.get('file', '')}"
        return src.get("file", "") or self.title


def load_service(path: Path, service_name: str | None = None) -> ServiceSpec:
    """Carga un OpenAPI y devuelve sus operaciones con el apiName como prefijo."""
    doc = yamlio.load(path)
    if not isinstance(doc, dict) or "paths" not in doc:
        raise ValueError(f"{path}: no parece un documento OpenAPI (falta 'paths')")
    base = base_path_from_servers(doc.get("servers"))
    # apiName = primer segmento del base path ('/nnrf-nfm/v1' -> 'nnrf-nfm').
    name = service_name or base.strip("/").split("/")[0]
    info = doc.get("info") or {}
    ops: list[Operation] = []
    for tmpl, item in (doc.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        if "$ref" in item and not any(m in item for m in HTTP_METHODS):
            # Referencia externa sin resolver (p. ej. TS29504 -> TS29505): la
            # saltamos; make_extracts.py ya la resuelve en los extractos.
            continue
        for method in HTTP_METHODS:
            if method not in item:
                continue
            op = item[method] or {}
            ops.append(
                Operation(
                    service=name,
                    base_path=base,
                    method=method.upper(),
                    path_template=str(tmpl),
                    operation_id=str(op.get("operationId", "")),
                    summary=str(op.get("summary", "")),
                )
            )
    source = dict(doc.get("x-spec2policy") or {})
    source.setdefault("file", path.name)
    return ServiceSpec(
        name=name,
        title=str(info.get("title", "")),
        version=str(info.get("version", "")),
        base_path=base,
        operations=ops,
        source=source,
    )


def find_operation(spec: ServiceSpec, method: str, path: str) -> Operation | None:
    for op in spec.operations:
        if op.matches(method, path):
            return op
    return None

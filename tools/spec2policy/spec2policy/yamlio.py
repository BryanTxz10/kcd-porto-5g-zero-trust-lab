"""Utilidades de E/S YAML con el estilo del repo (secuencias indentadas, LF)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class _IndentedDumper(yaml.SafeDumper):
    """Indenta las secuencias bajo su clave, como los manifiestos de cilium-policies/."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:  # noqa: ARG002
        super().increase_indent(flow, False)


def dump(data: Any, *, width: int = 100) -> str:
    return yaml.dump(
        data,
        Dumper=_IndentedDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=width,
    )


def write_text(path: Path, text: str) -> None:
    """Escribe siempre con LF (el repo fuerza eol=lf; en Windows evitamos CRLF)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)

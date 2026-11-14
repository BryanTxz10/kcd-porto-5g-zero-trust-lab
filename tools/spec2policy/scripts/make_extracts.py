#!/usr/bin/env python3
"""Genera los extractos OpenAPI de data/openapi/ desde el mirror jdegre/5GC_APIs.

No vendorizamos el mirror entero: de cada fichero conservamos solo lo que
spec2policy necesita (info, servers y paths con método/operationId/summary).
Se eliminan esquemas, parámetros, cuerpos y respuestas. El commit del mirror
queda fijado en PINNED_COMMIT y se escribe en cada extracto (x-spec2policy).

Uso (requiere red):
    python scripts/make_extracts.py [--out data/openapi]

Los path items que son $ref a otro fichero (p. ej. TS29504_Nudr_DR.yaml ->
TS29505_Subscription_Data.yaml) se resuelven descargando el fichero referido.
"""

from __future__ import annotations

import argparse
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from spec2policy import yamlio  # noqa: E402

MIRROR = "jdegre/5GC_APIs"
# Rama Rel-17 del mirror, fijada por commit (2024-06-08).
PINNED_COMMIT = "06137ac51e2cc19a6d767bb63a27563d27841b3a"
RAW = f"https://raw.githubusercontent.com/{MIRROR}/{PINNED_COMMIT}/"

HTTP_METHODS = ("get", "put", "post", "delete", "patch", "head", "options")

# Fichero -> prefijos de path a conservar (None = todos). Para el UDR solo
# interesan los datos de suscripción y de política que usan UDM y PCF.
FILES: dict[str, list[str] | None] = {
    "TS29510_Nnrf_NFManagement.yaml": None,
    "TS29510_Nnrf_NFDiscovery.yaml": None,
    "TS29509_Nausf_UEAuthentication.yaml": None,
    "TS29503_Nudm_UEAU.yaml": None,
    "TS29503_Nudm_UECM.yaml": None,
    "TS29503_Nudm_SDM.yaml": None,
    "TS29504_Nudr_DR.yaml": ["/subscription-data/", "/policy-data/"],
    "TS29502_Nsmf_PDUSession.yaml": None,
    "TS29518_Namf_Communication.yaml": None,
    "TS29507_Npcf_AMPolicyControl.yaml": None,
    "TS29512_Npcf_SMPolicyControl.yaml": None,
    "TS29531_Nnssf_NSSelection.yaml": None,
    "TS29521_Nbsf_Management.yaml": None,
}


def fetch(name: str, cache: dict[str, dict]) -> dict:
    """Descarga y parsea un fichero del mirror (con caché en memoria)."""
    if name not in cache:
        with urllib.request.urlopen(RAW + name, timeout=60) as resp:
            cache[name] = yaml.safe_load(resp.read().decode("utf-8"))
    return cache[name]


def resolve_path_item(item: dict, cache: dict[str, dict], resolved: set[str]) -> dict:
    """Resuelve un path item que es $ref externo ('Fichero.yaml#/paths/~1x~1y')."""
    ref = item.get("$ref")
    if not ref or "#" not in ref:
        return item
    fname, pointer = ref.split("#", 1)
    resolved.add(fname)
    node = fetch(fname, cache)
    # JSON Pointer (RFC 6901): ~1 -> '/', ~0 -> '~'; el mirror además codifica
    # las llaves de los parámetros como %7B/%7D.
    for part in pointer.strip("/").split("/"):
        key = urllib.parse.unquote(part).replace("~1", "/").replace("~0", "~")
        node = node[key]
    return node


def extract(name: str, prefixes: list[str] | None, cache: dict[str, dict]) -> dict:
    doc = fetch(name, cache)
    resolved: set[str] = set()
    paths: dict[str, dict] = {}
    for path, item in (doc.get("paths") or {}).items():
        if prefixes and not any(path.startswith(p) for p in prefixes):
            continue
        item = resolve_path_item(item, cache, resolved)
        ops = {}
        for method in HTTP_METHODS:
            if method in item:
                op = item[method] or {}
                slim = {k: op[k] for k in ("operationId", "summary") if k in op}
                ops[method] = slim
        if ops:
            paths[path] = ops
    info = doc.get("info", {})
    out: dict = {
        "openapi": doc.get("openapi", "3.0.0"),
        "info": {k: info[k] for k in ("title", "version") if k in info},
    }
    if "externalDocs" in doc:
        out["externalDocs"] = doc["externalDocs"]
    out["servers"] = doc.get("servers", [])
    out["paths"] = paths
    out["x-spec2policy"] = {
        "source": MIRROR,
        "commit": PINNED_COMMIT,
        "file": name,
        "resolved_refs": sorted(resolved),
        "path_prefixes": prefixes or [],
    }
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    default_out = Path(__file__).resolve().parent.parent / "data" / "openapi"
    ap.add_argument("--out", type=Path, default=default_out)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    cache: dict[str, dict] = {}
    for name, prefixes in FILES.items():
        data = extract(name, prefixes, cache)
        header = (
            f"# Extracto generado por scripts/make_extracts.py desde {MIRROR}@{PINNED_COMMIT}\n"
            f"# Fichero origen: {name}. Solo se conservan info, servers y paths con\n"
            "# método/operationId/summary; se eliminan esquemas, parámetros y respuestas.\n"
            "# NO EDITAR A MANO: regenerar con el script.\n"
        )
        yamlio.write_text(args.out / name, header + yamlio.dump(data))
        print(f"ok  {name}: {len(data['paths'])} paths")
    return 0


if __name__ == "__main__":
    sys.exit(main())

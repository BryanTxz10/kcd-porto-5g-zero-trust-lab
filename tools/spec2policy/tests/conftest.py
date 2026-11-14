"""Fixtures compartidas: rutas del proyecto y objetos cargados una vez por sesión."""

from __future__ import annotations

from pathlib import Path

import pytest

from spec2policy.cli import load_specs
from spec2policy.hubble import load_files
from spec2policy.topology import load_topology

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FIXTURES = ROOT / "fixtures" / "hubble"
EXAMPLES = ROOT / "examples" / "out"


@pytest.fixture(scope="session")
def topo():
    return load_topology(DATA / "services.yaml")


@pytest.fixture(scope="session")
def specs(topo):
    return load_specs(topo, DATA / "openapi")


@pytest.fixture(scope="session")
def flows_sin_tls(topo):
    return load_files([FIXTURES / "sbi-sin-tls.jsonl"], sbi_port=topo.sbi_port)


@pytest.fixture(scope="session")
def flows_mtls(topo):
    return load_files([FIXTURES / "sbi-mtls-sin-l7.jsonl"], sbi_port=topo.sbi_port)

"""CLI de extremo a extremo y determinismo de los ejemplos commiteados."""

from __future__ import annotations

import filecmp
import subprocess
import sys

import pytest

from spec2policy.cli import main

from .conftest import DATA, EXAMPLES, FIXTURES, ROOT


def test_generate_en_tmp(tmp_path, capsys):
    rc = main(
        [
            "generate",
            "--openapi-dir",
            str(DATA / "openapi"),
            "--services",
            str(DATA / "services.yaml"),
            "--flows",
            str(FIXTURES / "sbi-sin-tls.jsonl"),
            "--out",
            str(tmp_path),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "CNP: 10" in out and "OBSERVADO_ORIGEN_INESPERADO=4" in out
    assert (tmp_path / "blast-radius-map.md").exists()
    assert (tmp_path / "blast-radius-map.csv").exists()
    cnps = sorted(p.name for p in (tmp_path / "cnp").glob("*.yaml"))
    assert "spec2policy-sbi-scp.yaml" in cnps and "spec2policy-sbi-l7-visibility.yaml" in cnps
    assert len(cnps) == 11


def test_generate_mtls_avisa(tmp_path, capsys):
    main(["generate", "--flows", str(FIXTURES / "sbi-mtls-sin-l7.jsonl"), "--out", str(tmp_path)])
    assert "sin visibilidad L7" in capsys.readouterr().out


def test_generate_observed_sin_l7_falla(tmp_path):
    with pytest.raises(ValueError):
        main(
            [
                "generate",
                "--mode",
                "observed",
                "--flows",
                str(FIXTURES / "sbi-mtls-sin-l7.jsonl"),
                "--out",
                str(tmp_path),
            ]
        )


def test_visibility_a_stdout(capsys):
    assert main(["visibility"]) == 0
    assert "spec2policy-sbi-l7-visibility" in capsys.readouterr().out


def test_inspect_flows(capsys):
    assert main(["inspect-flows", str(FIXTURES / "sbi-sin-tls.jsonl")]) == 0
    out = capsys.readouterr().out
    assert "l7_req=81" in out
    assert "amf -> scp    POST   /nausf-auth/v1/ue-authentications" in out


@pytest.mark.skipif(not EXAMPLES.exists(), reason="sin ejemplos commiteados")
def test_ejemplos_commiteados_estan_al_dia(tmp_path):
    """Lo mismo que hace `make spec2policy` + `git diff --exit-code` en CI."""
    cmd = [
        sys.executable,
        "-m",
        "spec2policy",
        "generate",
        "--flows",
        "fixtures/hubble/sbi-sin-tls.jsonl",
        "--out",
        str(tmp_path),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True)
    for rel in ["blast-radius-map.md", "blast-radius-map.csv"]:
        assert filecmp.cmp(tmp_path / rel, EXAMPLES / rel, shallow=False), rel
    generated = sorted(p.name for p in (tmp_path / "cnp").glob("*.yaml"))
    committed = sorted(p.name for p in (EXAMPLES / "cnp").glob("*.yaml"))
    assert generated == committed
    for name in generated:
        assert filecmp.cmp(tmp_path / "cnp" / name, EXAMPLES / "cnp" / name, shallow=False), name

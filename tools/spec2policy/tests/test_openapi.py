"""Carga de OpenAPI 3GPP y conversión de plantillas de path a regex."""

from __future__ import annotations

import re

import pytest

from spec2policy.openapi import (
    Operation,
    base_path_from_servers,
    escape_literal,
    find_operation,
    load_service,
    template_to_regex,
)

from .conftest import DATA


def test_base_path_quita_api_root():
    assert base_path_from_servers([{"url": "{apiRoot}/nnrf-nfm/v1"}]) == "/nnrf-nfm/v1"
    assert base_path_from_servers([{"url": "{apiRoot}/nudm-sdm/v2/"}]) == "/nudm-sdm/v2"


def test_base_path_sin_servers_falla():
    with pytest.raises(ValueError):
        base_path_from_servers(None)


def test_escape_literal_deja_guiones_y_barras():
    assert escape_literal("/nnrf-nfm/v1/nf-instances") == "/nnrf-nfm/v1/nf-instances"
    assert escape_literal("a.b+c") == r"a\.b\+c"


@pytest.mark.parametrize(
    ("template", "allow_query", "regex"),
    [
        ("/nnrf-nfm/v1/nf-instances", False, "/nnrf-nfm/v1/nf-instances"),
        ("/nnrf-nfm/v1/nf-instances", True, r"/nnrf-nfm/v1/nf-instances(\?.*)?"),
        ("/nudm-sdm/v2/{supi}/am-data", False, "/nudm-sdm/v2/[^/]+/am-data"),
        ("/nudm-sdm/v2/{supi}/am-data", True, r"/nudm-sdm/v2/[^/?]+/am-data(\?.*)?"),
        (
            "/nudr-dr/v2/subscription-data/{ueId}/{servingPlmnId}/provisioned-data/am-data",
            False,
            "/nudr-dr/v2/subscription-data/[^/]+/[^/]+/provisioned-data/am-data",
        ),
    ],
)
def test_template_to_regex(template, allow_query, regex):
    assert template_to_regex(template, allow_query=allow_query) == regex


def test_regex_con_query_hace_fullmatch_del_pseudo_header_path():
    rx = template_to_regex("/nnrf-disc/v1/nf-instances")
    assert re.fullmatch(rx, "/nnrf-disc/v1/nf-instances?target-nf-type=AUSF&requester-nf-type=AMF")
    assert re.fullmatch(rx, "/nnrf-disc/v1/nf-instances")
    assert not re.fullmatch(rx, "/nnrf-disc/v1/nf-instances/extra")


def test_parametro_no_cruza_barras():
    op = Operation("nudm-sdm", "/nudm-sdm/v2", "GET", "/{supi}/am-data")
    assert op.matches("GET", "/nudm-sdm/v2/imsi-999700000000001/am-data")
    assert not op.matches("GET", "/nudm-sdm/v2/a/b/am-data")
    assert not op.matches("POST", "/nudm-sdm/v2/imsi-999700000000001/am-data")


def test_carga_extracto_nnrf_nfm():
    spec = load_service(DATA / "openapi" / "TS29510_Nnrf_NFManagement.yaml", "nnrf-nfm")
    assert spec.base_path == "/nnrf-nfm/v1"
    methods = {(o.method, o.path_template) for o in spec.operations}
    assert ("PUT", "/nf-instances/{nfInstanceID}") in methods
    assert ("PATCH", "/nf-instances/{nfInstanceID}") in methods
    assert ("POST", "/subscriptions") in methods
    assert spec.source["commit"].startswith("06137ac5")
    assert spec.source_label.startswith("jdegre/5GC_APIs@06137ac51e2c:")


def test_find_operation_resuelve_registro_nrf():
    spec = load_service(DATA / "openapi" / "TS29510_Nnrf_NFManagement.yaml", "nnrf-nfm")
    op = find_operation(
        spec, "put", "/nnrf-nfm/v1/nf-instances/6f3e9c2a-1b7d-4e55-9a10-2c9b7f1d0e01"
    )
    assert op is not None and op.operation_id == "RegisterNFInstance"
    assert find_operation(spec, "GET", "/nnrf-nfm/v1/no-existe") is None


def test_nudr_dr_resuelve_refs_externas_y_es_v2():
    spec = load_service(DATA / "openapi" / "TS29504_Nudr_DR.yaml", "nudr-dr")
    assert spec.base_path == "/nudr-dr/v2"
    templates = {o.path_template for o in spec.operations}
    # TS29505 (subscription-data) y TS29519 (policy-data), resueltos por make_extracts.py
    assert "/subscription-data/{ueId}/authentication-data/authentication-subscription" in templates
    assert "/policy-data/ues/{ueId}/sm-data" in templates


def test_todos_los_extractos_tienen_procedencia(topo, specs):
    assert set(specs) == set(topo.services)
    for s in specs.values():
        assert s.source["source"] == "jdegre/5GC_APIs"
        assert s.source["commit"] == "06137ac51e2cc19a6d767bb63a27563d27841b3a"
        assert s.operations, s.name

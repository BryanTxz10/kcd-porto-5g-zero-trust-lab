"""Cruce estándar/observado, generación de CNP e informe."""

from __future__ import annotations

import csv
import io

import pytest
import yaml

from spec2policy.analysis import (
    ST_CONFORME,
    ST_INESPERADO,
    ST_NO_OBSERVADO,
    UN_FUERA_ESTANDAR,
    analyze,
    blast_radius,
    build_rows,
)
from spec2policy.policy import (
    MODE_OBSERVED,
    MODE_STANDARD,
    PolicyOptions,
    build_all,
    build_visibility_policy,
    render,
)
from spec2policy.report import CSV_COLUMNS, MTLS_WARNING, to_csv, to_markdown


@pytest.fixture(scope="module")
def analysis(topo, specs, flows_sin_tls):
    return analyze(
        topo, specs, flows_sin_tls.flows, flows_sin_tls.stats, ["fixtures/hubble/sbi-sin-tls.jsonl"]
    )


@pytest.fixture(scope="module")
def analysis_mtls(topo, specs, flows_mtls):
    return analyze(topo, specs, flows_mtls.flows, flows_mtls.stats, ["x.jsonl"])


def _row(analysis, at, method, template):
    hits = [
        r
        for r in analysis.rows
        if r.at == at and r.method == method and r.path_template == template
    ]
    assert len(hits) == 1, (at, method, template, len(hits))
    return hits[0]


# --- filas ----------------------------------------------------------------------------


def test_operaciones_via_scp_aparecen_en_productor_y_en_scp(topo, specs):
    rows = build_rows(topo, specs)
    sdm = [
        r
        for r in rows
        if r.service == "nudm-sdm" and r.path_template == "/nudm-sdm/v2/{supi}/am-data"
    ]
    assert {r.at for r in sdm} == {"udm", "scp"}
    en_udm = next(r for r in sdm if r.at == "udm")
    en_scp = next(r for r in sdm if r.at == "scp")
    assert en_udm.expected_sources == ["scp"]  # colapso: el UDM solo ve al SCP
    assert en_scp.expected_sources == ["amf", "smf"]  # consumidores reales


def test_nnrf_nfm_es_directo_y_no_se_duplica_en_scp(topo, specs):
    rows = build_rows(topo, specs)
    reg = [r for r in rows if r.service == "nnrf-nfm" and r.method == "PUT"]
    assert [r.at for r in reg] == ["nrf"]
    assert "scp" in reg[0].expected_sources and "amf" in reg[0].expected_sources


def test_callbacks_generan_filas_en_el_receptor(topo, specs):
    rows = build_rows(topo, specs)
    cb = [r for r in rows if r.kind == "callback" and r.at == "smf"]
    assert {r.service for r in cb} == {
        "callback:nnrf-nfm-status-notify",
        "callback:npcf-sm-policy-notify",
    }
    assert next(r for r in cb if "npcf" in r.service).expected_sources == ["pcf"]


# --- cruce ------------------------------------------------------------------------------


def test_estados_del_fixture(analysis):
    counts = analysis.status_counts()
    assert counts[ST_INESPERADO] == 4
    assert counts[ST_CONFORME] == 57
    assert counts[ST_NO_OBSERVADO] + counts[ST_CONFORME] + counts[ST_INESPERADO] == len(
        analysis.rows
    )
    assert [u.reason for u in analysis.unmatched] == [UN_FUERA_ESTANDAR]
    assert analysis.unmatched[0].flow.path == "/nudm-sdm/v2/admin/dump"


def test_impostor_sin_label_es_origen_inesperado(analysis, topo):
    r = _row(analysis, "nrf", "GET", "/nnrf-nfm/v1/nf-instances")
    assert r.status == ST_INESPERADO
    assert r.unexpected_sources == ["?(netshoot)"]
    assert r.explain_source(topo, "?(netshoot)") == "sin label de identidad de NF"


def test_consumidor_legitimo_que_salta_el_scp(analysis, topo):
    r = _row(analysis, "udm", "GET", "/nudm-sdm/v2/{supi}/am-data")
    assert r.status == ST_INESPERADO
    assert r.unexpected_sources == ["amf"]
    assert "sin pasar por el SCP" in r.explain_source(topo, "amf")
    assert r.observed["scp"] == 1  # el tráfico legítimo también está


def test_no_consumidor_solo_se_detecta_en_la_entrada_del_scp(analysis, topo):
    tmpl = "/nudr-dr/v2/subscription-data/{ueId}/context-data/amf-3gpp-access"
    en_scp = _row(analysis, "scp", "PATCH", tmpl)
    en_udr = _row(analysis, "udr", "PATCH", tmpl)
    assert en_scp.status == ST_INESPERADO and en_scp.unexpected_sources == ["smf"]
    assert "no es consumidor" in en_scp.explain_source(topo, "smf")
    assert en_udr.status == ST_CONFORME  # el UDR lo ve llegar del SCP: no puede saber más


def test_flujo_conforme(analysis):
    r = _row(analysis, "ausf", "POST", "/nausf-auth/v1/ue-authentications")
    assert r.status == ST_CONFORME and dict(r.observed) == {"scp": 1}


def test_sin_flujos_todo_no_observado(topo, specs):
    a = analyze(topo, specs, None)
    assert set(a.status_counts()) == {ST_NO_OBSERVADO}
    assert a.unmatched == []


def test_blast_radius(topo, analysis):
    br = {b.consumer: b for b in blast_radius(topo, analysis)}
    assert br["amf"].producers_std == ["ausf", "nrf", "nssf", "pcf", "smf", "udm"]
    assert br["amf"].ops_std > br["ausf"].ops_std > 0
    assert br["amf"].ops_observed == 14
    # Todo el que pasa por el SCP alcanza, tras el colapso, lo mismo: lo que el SCP puede pedir.
    assert len({b.ops_scp_collapse for b in br.values()}) == 1
    assert br["bsf"].ops_scp_collapse > br["bsf"].ops_std


# --- CNP --------------------------------------------------------------------------------


def test_cnp_standard_udm_solo_desde_scp_y_nrf(topo, specs, analysis):
    policies = build_all(topo, analysis, specs, PolicyOptions(mode=MODE_STANDARD))
    assert set(policies) == set(topo.nfs)
    header, cnp = policies["udm"]
    assert "NO verificado en clúster" in header
    assert cnp["metadata"]["name"] == "spec2policy-sbi-udm"
    assert cnp["metadata"]["labels"]["cib46.io/managed"] == "true"
    assert cnp["spec"]["endpointSelector"] == {"matchLabels": {"app.kubernetes.io/name": "udm"}}
    sources = [
        i["fromEndpoints"][0]["matchLabels"]["app.kubernetes.io/name"]
        for i in cnp["spec"]["ingress"]
    ]
    assert sources == ["nrf", "scp"]
    for i in cnp["spec"]["ingress"]:
        sel = i["fromEndpoints"][0]["matchLabels"]
        assert sel["io.kubernetes.pod.namespace"] == "5g-cp" and sel["cib46-nf-type"] == "core-nf"
        assert i["toPorts"][0]["ports"] == [{"port": "7777", "protocol": "TCP"}]
    http = cnp["spec"]["ingress"][1]["toPorts"][0]["rules"]["http"]
    assert {"method": "GET", "path": r"/nudm-sdm/v2/[^/?]+/am-data(\?.*)?"} in http
    assert http == sorted(http, key=lambda r: (r["method"], r["path"]))


def test_cnp_scp_autoriza_por_consumidor(topo, specs, analysis):
    _, cnp = build_all(topo, analysis, specs, PolicyOptions())["scp"]
    por_origen = {
        i["fromEndpoints"][0]["matchLabels"]["app.kubernetes.io/name"]: i["toPorts"][0]["rules"][
            "http"
        ]
        for i in cnp["spec"]["ingress"]
    }
    assert {"method": "POST", "path": r"/nausf-auth/v1/ue-authentications(\?.*)?"} in por_origen[
        "amf"
    ]
    assert not any("nausf-auth" in r["path"] for r in por_origen["smf"])
    assert not any("nudr-dr" in r["path"] for r in por_origen["smf"])  # el SMF no consume nudr-dr
    assert any("nudr-dr" in r["path"] for r in por_origen["udm"])


def test_cnp_nrf_lista_cada_consumidor_directo(topo, specs, analysis):
    _, cnp = build_all(topo, analysis, specs, PolicyOptions())["nrf"]
    sources = sorted(
        i["fromEndpoints"][0]["matchLabels"]["app.kubernetes.io/name"]
        for i in cnp["spec"]["ingress"]
    )
    assert sources == sorted(topo.services["nnrf-nfm"].consumers)


def test_cnp_observed_es_subconjunto(topo, specs, analysis):
    std = build_all(topo, analysis, specs, PolicyOptions(mode=MODE_STANDARD))
    obs = build_all(topo, analysis, specs, PolicyOptions(mode=MODE_OBSERVED))

    def rules(p):
        out = set()
        for i in p["spec"]["ingress"]:
            src = i["fromEndpoints"][0]["matchLabels"]["app.kubernetes.io/name"]
            for r in i["toPorts"][0]["rules"]["http"]:
                out.add((src, r["method"], r["path"]))
        return out

    for nf, (_, p) in obs.items():
        assert rules(p) <= rules(std[nf][1])
    # El AMF directo al UDM no entra en 'observed': no venía del origen esperado.
    assert not any(src == "amf" for src, _, _ in rules(obs["udm"][1]))
    assert len(rules(obs["udm"][1])) < len(rules(std["udm"][1]))


def test_observed_sin_l7_falla(topo, specs, analysis_mtls):
    with pytest.raises(ValueError, match="sin flujos L7"):
        build_all(topo, analysis_mtls, specs, PolicyOptions(mode=MODE_OBSERVED))


def test_sin_query_suffix(topo, specs, analysis):
    _, cnp = build_all(topo, analysis, specs, PolicyOptions(allow_query=False))["ausf"]
    paths = [r["path"] for i in cnp["spec"]["ingress"] for r in i["toPorts"][0]["rules"]["http"]]
    assert all("(\\?.*)?" not in p for p in paths)
    assert "/nausf-auth/v1/ue-authentications/[^/]+/5g-aka-confirmation" in paths


def test_render_es_yaml_valido_con_cabecera(topo, specs, analysis):
    header, cnp = build_all(topo, analysis, specs, PolicyOptions())["bsf"]
    text = render(header, cnp)
    assert text.startswith("# Generado por tools/spec2policy")
    assert yaml.safe_load(text) == cnp


def test_visibility_policy(topo):
    header, cnp = build_visibility_policy(topo)
    assert "mTLS" in header
    expr = cnp["spec"]["endpointSelector"]["matchExpressions"][0]
    assert expr["key"] == "app.kubernetes.io/name" and set(expr["values"]) == set(topo.nfs)
    assert cnp["spec"]["ingress"][0]["toPorts"][0]["rules"] == {"http": [{}]}


# --- informe ------------------------------------------------------------------------------


def test_csv_columnas_y_filas(analysis):
    rows = list(csv.DictReader(io.StringIO(to_csv(analysis))))
    assert list(rows[0]) == CSV_COLUMNS
    assert len(rows) == len(analysis.rows) + len(analysis.unmatched)
    estados = {r["estado"] for r in rows}
    assert {ST_CONFORME, ST_INESPERADO, ST_NO_OBSERVADO, UN_FUERA_ESTANDAR} <= estados
    fila = next(
        r
        for r in rows
        if r["punto_de_entrada"] == "udm" and r["path"] == "/nudm-sdm/v2/{supi}/am-data"
    )
    assert fila["origen_esperado"] == "scp" and fila["observado_desde"] == "amf:1;scp:1"
    assert fila["consumidores_estandar"] == "amf;smf" and fila["ruta"] == "scp"


def test_markdown_secciones_y_hallazgos(topo, specs, analysis):
    md = to_markdown(topo, analysis, specs)
    for h in (
        "## Fuentes",
        "## Captura",
        "## Efecto del SCP",
        "## Resumen",
        "## Radio de impacto por consumidor comprometido",
        "## Hallazgos (diferencia)",
        "## Limitaciones",
    ):
        assert h in md
    assert "jdegre/5GC_APIs@06137ac51e2c" in md
    assert "sin pasar por el SCP" in md
    assert "`/nudm-sdm/v2/admin/dump`" in md
    assert MTLS_WARNING not in md


def test_markdown_avisa_de_ceguera_mtls(topo, specs, analysis_mtls):
    md = to_markdown(topo, analysis_mtls, specs)
    assert MTLS_WARNING in md
    assert "_Nada observado en L7._" in md

"""Tabla productor/consumidor y modelado del SCP."""

from __future__ import annotations

import pytest

from spec2policy import yamlio
from spec2policy.topology import ROUTE_DIRECT, ROUTE_SCP, load_topology


def test_tabla_del_testbed_es_coherente(topo):
    assert topo.namespace == "5g-cp"
    assert topo.sbi_port == 7777
    assert set(topo.nfs) == {"nrf", "scp", "amf", "smf", "ausf", "udm", "udr", "pcf", "nssf", "bsf"}
    assert topo.nfs["udm"].service == "open5gs-cp-udm-sbi"
    assert topo.producers() == sorted(
        {"nrf", "ausf", "udm", "udr", "smf", "amf", "pcf", "nssf", "bsf"}
    )


def test_scp_modelo_d_solo_nnrf_nfm_directo(topo):
    assert topo.scp is not None and topo.scp.nf == "scp"
    assert topo.route_of("nnrf-nfm") == ROUTE_DIRECT
    assert topo.route_of("nnrf-disc") == ROUTE_SCP
    assert topo.route_of("nudm-sdm") == ROUTE_SCP
    # En el productor, el origen esperado de todo lo que va vía SCP es el SCP.
    assert topo.expected_sources("nudm-sdm") == ["scp"]
    assert topo.expected_sources("nnrf-nfm") == sorted(topo.services["nnrf-nfm"].consumers)


def test_selectores_coinciden_con_cnp_existentes(topo):
    assert topo.peer_selector("amf") == {
        "io.kubernetes.pod.namespace": "5g-cp",
        "cib46-nf-type": "core-nf",
        "app.kubernetes.io/name": "amf",
    }
    assert topo.endpoint_selector("udm") == {"app.kubernetes.io/name": "udm"}


def test_consumidores_citan_ts_23_502(topo):
    assert topo.services["nausf-auth"].consumers == ["amf"]
    assert set(topo.services["nudr-dr"].consumers) == {"udm", "pcf"}
    assert {s.name for s in topo.services_consumed_by("amf")} >= {
        "nausf-auth",
        "nudm-sdm",
        "nsmf-pdusession",
        "npcf-am-policy-control",
    }


def test_callbacks_apuntan_a_nf_conocidas(topo):
    names = {c.name for c in topo.callbacks}
    assert "nnrf-nfm-status-notify" in names
    assert all(c.method == "POST" for c in topo.callbacks)
    assert [c.name for c in topo.callbacks_to("smf")] == [
        "nnrf-nfm-status-notify",
        "npcf-sm-policy-notify",
    ]


def _write(tmp_path, doc):
    p = tmp_path / "services.yaml"
    yamlio.write_text(p, yamlio.dump(doc))
    return p


def test_valida_nf_desconocida(tmp_path):
    doc = {
        "nfs": {"nrf": {}, "amf": {}},
        "services": {"nnrf-nfm": {"producer": "nrf", "consumers": ["amf", "fantasma"]}},
    }
    with pytest.raises(ValueError, match="consumidor desconocido 'fantasma'"):
        load_topology(_write(tmp_path, doc))


def test_valida_productor_no_se_consume_a_si_mismo(tmp_path):
    doc = {"nfs": {"nrf": {}}, "services": {"nnrf-nfm": {"producer": "nrf", "consumers": ["nrf"]}}}
    with pytest.raises(ValueError, match="no puede consumirse a sí mismo"):
        load_topology(_write(tmp_path, doc))


def test_sin_scp_todo_es_directo(tmp_path):
    doc = {
        "nfs": {"nrf": {}, "amf": {}, "ausf": {}},
        "services": {"nausf-auth": {"producer": "ausf", "consumers": ["amf"]}},
    }
    topo = load_topology(_write(tmp_path, doc))
    assert topo.scp is None
    assert topo.route_of("nausf-auth") == ROUTE_DIRECT
    assert topo.expected_sources("nausf-auth") == ["amf"]

"""Parser de `hubble observe -o jsonpb`."""

from __future__ import annotations

import json

from spec2policy.hubble import nf_from_labels, parse_lines


def _l7(src, dst, method, url, *, wrapper=True, camel=False):
    def ep(nf):
        return {
            "namespace": "5g-cp",
            ("podName" if camel else "pod_name"): f"open5gs-cp-{nf}-x",
            "labels": [f"k8s:app.kubernetes.io/name={nf}", "k8s:io.kubernetes.pod.namespace=5g-cp"],
        }

    flow = {
        "verdict": "FORWARDED",
        "l4": {"TCP": {("destinationPort" if camel else "destination_port"): 7777}},
        "source": ep(src),
        "destination": ep(dst),
        "l7": {"type": "REQUEST", "http": {"method": method, "url": url, "protocol": "HTTP/2"}},
    }
    return json.dumps({"flow": flow, "time": "2026-11-19T09:00:00Z"} if wrapper else flow)


def test_nf_from_labels():
    assert nf_from_labels(["k8s:foo=bar", "k8s:app.kubernetes.io/name=amf"]) == "amf"
    assert nf_from_labels(["app.kubernetes.io/name=udm"]) == "udm"
    assert nf_from_labels(["k8s:run=netshoot"]) is None


def test_request_con_envoltorio_snake_case():
    r = parse_lines(
        [
            _l7(
                "amf",
                "scp",
                "POST",
                "http://open5gs-cp-scp-sbi:7777/nausf-auth/v1/ue-authentications",
            )
        ]
    )
    assert len(r.flows) == 1
    f = r.flows[0]
    assert (f.src_nf, f.dst_nf, f.method) == ("amf", "scp", "POST")
    assert f.path == "/nausf-auth/v1/ue-authentications"
    assert f.dst_port == 7777
    assert f.time == "2026-11-19T09:00:00Z"
    assert r.stats.l7_requests == 1 and r.stats.flows == 1


def test_request_sin_envoltorio_camel_case():
    r = parse_lines(
        [
            _l7(
                "scp",
                "nrf",
                "GET",
                "http://nrf:7777/nnrf-disc/v1/nf-instances?target-nf-type=UDM",
                wrapper=False,
                camel=True,
            )
        ]
    )
    f = r.flows[0]
    assert f.dst_pod == "open5gs-cp-nrf-x"
    assert f.path == "/nnrf-disc/v1/nf-instances"  # la query no forma parte del path
    assert "target-nf-type=UDM" in f.url


def test_ignora_respuestas_y_json_invalido_pero_los_cuenta():
    resp = json.loads(_l7("amf", "scp", "POST", "http://x/y"))
    resp["flow"]["l7"]["type"] = "RESPONSE"
    r = parse_lines(
        [json.dumps(resp), "{esto no es json", "", _l7("amf", "scp", "GET", "http://x/z")]
    )
    assert len(r.flows) == 1
    assert r.stats.l7_responses == 1
    assert r.stats.invalid_json == 1
    assert r.stats.lines == 3


def test_l34_hacia_sbi_sin_l7_dispara_ceguera():
    flow = {
        "verdict": "FORWARDED",
        "l4": {"TCP": {"destination_port": 7777}},
        "source": {},
        "destination": {},
    }
    other = {
        "verdict": "DROPPED",
        "l4": {"TCP": {"destination_port": 27017}},
        "source": {},
        "destination": {},
    }
    r = parse_lines([json.dumps({"flow": flow}), json.dumps({"flow": other})])
    assert r.flows == []
    assert r.stats.l34_sbi == 1 and r.stats.l34_other == 1 and r.stats.dropped == 1
    assert r.stats.by_verdict == {"FORWARDED": 1, "DROPPED": 1}
    assert r.stats.l7_blind


def test_fixture_sin_tls(flows_sin_tls):
    s = flows_sin_tls.stats
    assert s.l7_requests == 81 and s.l7_responses == 81
    assert s.l34_sbi == 4 and s.dropped == 1
    assert not s.l7_blind
    origenes = {f.src_label for f in flows_sin_tls.flows}
    assert "?(netshoot)" in origenes  # pod sin label de NF
    assert all(f.protocol == "HTTP/2" for f in flows_sin_tls.flows)


def test_fixture_mtls_no_tiene_l7(flows_mtls):
    assert flows_mtls.flows == []
    assert flows_mtls.stats.l34_sbi > 0
    assert flows_mtls.stats.l7_blind

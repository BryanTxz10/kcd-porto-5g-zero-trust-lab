#!/usr/bin/env python3
"""policy-matrix.py — matriz de flujos del lab en los dos modos, SIN clúster.

Construye los overlays de cilium-policies/lab/ (una-red = plan B,
deploy_multus: false; multus = redes dedicadas, deploy_multus: true) y evalúa,
para cada flujo legítimo y de ataque, si Cilium lo permitiría o lo descartaría,
y en qué sentido (egress del origen o ingress del destino).

Cada flujo trae lo ESPERADO en cada modo:
  ok      Cilium debe permitirlo.
  drop    Cilium debe descartarlo.
  multus  En ese modo el flujo no pasa por Cilium (N2, N3, N6 por interfaces
          de Multus; lo controla la Fase 2). Se comprueba igualmente que la
          red de pods NO lo permite: si un pod intentara ese flujo por eth0,
          Cilium lo descartaría.

ES UNA APROXIMACIÓN, no Cilium:
  - Solo L3/L4 (selectores de endpoints, entidades world y puertos).
  - No evalúa reglas L7 (HTTP), ni conntrack, ni autenticación mutua.
  - Las etiquetas de los pods están escritas a mano (función eps).
La verdad la da Hubble en el lab (docs/pruebas-fase3.md).

Uso:  python3 bootstrap/checks/policy-matrix.py [raíz_del_repo]
      make policy-matrix
Sale con código 1 si algún flujo no da lo esperado en algún modo.
"""

import os
import sys

import yaml

REPO = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
LAB = os.path.join(REPO, "cilium-policies", "lab")
MODES = ["una-red", "multus"]


def load(path):
    """Lee un directorio de Kustomize (resources: ficheros o directorios)."""
    k = yaml.safe_load(open(os.path.join(path, "kustomization.yaml")))
    out = []
    for r in k["resources"]:
        p = os.path.normpath(os.path.join(path, r))
        if os.path.isdir(p):
            out += load(p)
        else:
            out += [d for d in yaml.safe_load_all(open(p)) if d]
    return out


def ep(ns, name, **extra):
    labels = {"io.kubernetes.pod.namespace": ns, "app.kubernetes.io/name": name}
    labels.update(extra)
    return labels


def eps():
    cp = {"app.kubernetes.io/instance": "open5gs-cp"}
    e = {
        n: ep("5g-cp", n, **cp)
        for n in ["amf", "smf", "nrf", "scp", "udm", "udr", "ausf", "pcf", "bsf", "nssf"]
    }
    e["mongodb"] = ep("5g-cp", "mongodb", **cp)
    e["populate"] = ep("5g-cp", "open5gs", **{"app.kubernetes.io/component": "populate"})
    e["impostor"] = ep("5g-cp", "nf-impostor")  # pod en 5g-cp sin identidad de NF
    e["probe"] = ep("5g-cp", "sbi-probe")  # pod de prueba de la SBI (Fase 4)
    e["upf"] = ep("5g-up", "upf", **{"app.kubernetes.io/instance": "open5gs-up"})
    e["gnb"] = ep("5g-ran", "ueransim-gnb")
    e["ue"] = ep("5g-ran", "ueransim-ue")
    e["attacker"] = ep("5g-ran", "attacker-ue-lateral")
    e["dns"] = {"io.kubernetes.pod.namespace": "kube-system", "k8s-app": "kube-dns"}
    e["world"] = None
    e["apiserver"] = "kube-apiserver"
    return e


def sel(selector, labels, polns):
    if not isinstance(labels, dict):
        return False
    selector = selector or {}
    ml = dict(selector.get("matchLabels") or {})
    exprs = selector.get("matchExpressions") or []
    # En una CNP con namespace, un selector sin namespace es del mismo namespace.
    if "io.kubernetes.pod.namespace" not in ml and not any(
        x["key"] == "io.kubernetes.pod.namespace" for x in exprs
    ):
        ml["io.kubernetes.pod.namespace"] = polns
    if any(labels.get(k) != v for k, v in ml.items()):
        return False
    for x in exprs:
        v = labels.get(x["key"])
        if x["operator"] == "NotIn" and v in x["values"]:
            return False
        if x["operator"] == "In" and v not in x["values"]:
            return False
    return True


def ports_ok(rule, port, proto):
    tp = rule.get("toPorts")
    if not tp:
        return True
    return any(
        str(p["port"]) == str(port) and p.get("protocol", "ANY") in (proto, "ANY")
        for t in tp
        for p in t["ports"]
    )


def peer_ok(rule, peer, polns, direction):
    if not rule:  # regla vacía ({}): activa el enforcement, no permite nada
        return False
    key = "fromEndpoints" if direction == "ingress" else "toEndpoints"
    ent = "fromEntities" if direction == "ingress" else "toEntities"
    for e in rule.get(ent) or []:
        if e == "all" or (e == "world" and peer is None) or e == peer:
            return True
    return any(sel(s, peer, polns) for s in rule.get(key) or [])


def verdict(pols, e, s, d, port, proto):
    src, dst = e[s], e[d]
    for direction, me, peer in (("egress", src, dst), ("ingress", dst, src)):
        if not isinstance(me, dict):
            continue
        ps = [
            p
            for p in pols
            if direction in p["spec"]
            and sel(p["spec"].get("endpointSelector"), me, p["metadata"]["namespace"])
        ]
        if not ps:
            continue  # sin política en esa dirección: permitido
        if not any(
            peer_ok(r, peer, p["metadata"]["namespace"], direction) and ports_ok(r, port, proto)
            for p in ps
            for r in p["spec"][direction]
        ):
            return f"DROP({direction})"
    return "ok"


# (origen, destino, puerto, protocolo, esperado una-red, esperado multus)
SBI = [
    ("amf", "scp"), ("scp", "nrf"), ("scp", "udm"), ("scp", "ausf"), ("scp", "smf"),
    ("scp", "pcf"), ("nrf", "amf"), ("nssf", "scp"), ("amf", "nrf"), ("smf", "nrf"),
]
LEGIT = [(a, b, 7777, "TCP", "ok", "ok") for a, b in SBI] + [
    ("udr", "mongodb", 27017, "TCP", "ok", "ok"),
    ("pcf", "mongodb", 27017, "TCP", "ok", "ok"),
    ("populate", "mongodb", 27017, "TCP", "ok", "ok"),
    ("gnb", "amf", 38412, "SCTP", "ok", "multus"),
    ("gnb", "upf", 2152, "UDP", "ok", "multus"),
    ("upf", "gnb", 2152, "UDP", "ok", "multus"),
    ("upf", "world", 443, "TCP", "ok", "multus"),
    ("smf", "upf", 8805, "UDP", "ok", "ok"),
    ("ue", "gnb", 4997, "UDP", "ok", "ok"),
    ("gnb", "ue", 4997, "UDP", "ok", "ok"),
    ("amf", "dns", 53, "UDP", "ok", "ok"),
    ("smf", "dns", 53, "UDP", "ok", "ok"),
    ("gnb", "dns", 53, "UDP", "ok", "ok"),
    ("ue", "dns", 53, "UDP", "ok", "ok"),
    ("probe", "nrf", 7777, "TCP", "ok", "ok"),
    ("probe", "dns", 53, "UDP", "ok", "ok"),
]
ATTACK = [
    (a, b, p, pr, "drop", "drop")
    for a, b, p, pr in [
        ("attacker", "nrf", 7777, "TCP"),
        ("attacker", "mongodb", 27017, "TCP"),
        ("attacker", "amf", 38412, "SCTP"),
        ("attacker", "upf", 2152, "UDP"),
        ("attacker", "upf", 8805, "UDP"),
        ("attacker", "world", 443, "TCP"),
        ("attacker", "apiserver", 6443, "TCP"),
        ("gnb", "nrf", 7777, "TCP"),
        ("ue", "nrf", 7777, "TCP"),
        ("impostor", "nrf", 7777, "TCP"),
        ("impostor", "udm", 7777, "TCP"),
        ("impostor", "mongodb", 27017, "TCP"),
        ("impostor", "world", 443, "TCP"),
        ("impostor", "apiserver", 6443, "TCP"),
        ("upf", "nrf", 7777, "TCP"),
        ("upf", "mongodb", 27017, "TCP"),
        ("upf", "smf", 8805, "UDP"),
        ("upf", "dns", 53, "UDP"),
        ("upf", "apiserver", 6443, "TCP"),
        ("amf", "world", 443, "TCP"),
        ("amf", "apiserver", 6443, "TCP"),
        ("amf", "upf", 8805, "UDP"),
        ("bsf", "mongodb", 27017, "TCP"),
        ("probe", "udm", 7777, "TCP"),
        ("probe", "mongodb", 27017, "TCP"),
        ("probe", "world", 443, "TCP"),
    ]
]


def check(got, want):
    if want == "ok":
        return got == "ok"
    return got.startswith("DROP")  # 'drop' y 'multus': la red de pods no lo deja pasar


def main():
    pols = {m: load(os.path.join(LAB, m)) for m in MODES}
    e = eps()
    fallos = []
    for title, flows in (("TRÁFICO LEGÍTIMO", LEGIT), ("ATAQUES / NO PERMITIDO", ATTACK)):
        print(f"\n== {title} ==\n{'flujo':34}" + "".join(f"{m:22}" for m in MODES))
        for s, d, port, proto, *want in flows:
            name = f"{s} -> {d}:{port}/{proto}"
            cells = []
            for m, w in zip(MODES, want):
                got = verdict(pols[m], e, s, d, port, proto)
                txt = f"Multus [{got}]" if w == "multus" else got
                if not check(got, w):
                    txt += " ✗"
                    fallos.append(f"{m}: {name} esperado {w}, sale {got}")
                cells.append(f"{txt:22}")
            print(f"{name:34}" + "".join(cells))
    print("\nMultus [DROP(...)]: el flujo va por una interfaz de Multus; la red de pods no lo permite.")
    if fallos:
        print("\nERROR: flujos que no dan lo esperado:")
        for f in fallos:
            print(f"  - {f}")
        sys.exit(1)
    print("\nOK: todos los flujos dan lo esperado en los dos modos (aproximación L3/L4).")


if __name__ == "__main__":
    main()

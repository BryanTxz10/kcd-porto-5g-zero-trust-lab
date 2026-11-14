"""Tabla productor/consumidor por servicio (data/services.yaml) y modelado del SCP."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from spec2policy import yamlio

ROUTE_SCP = "scp"
ROUTE_DIRECT = "direct"


@dataclass(frozen=True)
class NF:
    name: str
    deployment: str = ""
    service: str = ""


@dataclass
class ServiceEntry:
    name: str
    producer: str
    consumers: list[str]
    spec: str = ""
    openapi: str = ""
    nota: str = ""


@dataclass
class Callback:
    name: str
    notifier: str
    receivers: list[str]
    method: str
    path: str
    route: str = ROUTE_DIRECT
    nota: str = ""


@dataclass
class ScpModel:
    nf: str = "scp"
    model: str = "D"
    direct_services: list[str] = field(default_factory=list)


@dataclass
class Topology:
    namespace: str
    sbi_port: int
    label_nf_name: str
    label_namespace: str
    identity_labels: dict[str, str]
    nfs: dict[str, NF]
    services: dict[str, ServiceEntry]
    callbacks: list[Callback]
    scp: ScpModel | None
    source_path: str = ""

    # --- consultas -----------------------------------------------------------
    def route_of(self, service: str) -> str:
        """'scp' si la petición llega al productor desde el SCP; 'direct' si no."""
        if self.scp is None or service in self.scp.direct_services:
            return ROUTE_DIRECT
        return ROUTE_SCP

    def expected_sources(self, service: str) -> list[str]:
        """Orígenes L3 que verá el productor para ese servicio."""
        entry = self.services[service]
        if self.route_of(service) == ROUTE_SCP:
            assert self.scp is not None
            return [self.scp.nf]
        return sorted(entry.consumers)

    def services_of_producer(self, nf: str) -> list[ServiceEntry]:
        return [s for s in self.services.values() if s.producer == nf]

    def services_consumed_by(self, nf: str) -> list[ServiceEntry]:
        return [s for s in self.services.values() if nf in s.consumers]

    def producers(self) -> list[str]:
        return sorted({s.producer for s in self.services.values()})

    def callbacks_to(self, nf: str) -> list[Callback]:
        return [c for c in self.callbacks if nf in c.receivers]

    def peer_selector(self, nf: str) -> dict[str, str]:
        """matchLabels de un fromEndpoints, con el mismo criterio que c2/c3."""
        sel = {self.label_namespace: self.namespace}
        sel.update(self.identity_labels)
        sel[self.label_nf_name] = nf
        return sel

    def endpoint_selector(self, nf: str) -> dict[str, str]:
        return {self.label_nf_name: nf}


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def load_topology(path: Path) -> Topology:
    doc = yamlio.load(path)
    if not isinstance(doc, dict) or "services" not in doc:
        raise ValueError(f"{path}: falta la sección 'services'")
    labels = doc.get("labels") or {}
    nfs = {
        str(name): NF(
            name=str(name),
            deployment=str((meta or {}).get("deployment", "")),
            service=str((meta or {}).get("service", "")),
        )
        for name, meta in (doc.get("nfs") or {}).items()
    }
    services: dict[str, ServiceEntry] = {}
    for name, meta in doc["services"].items():
        meta = meta or {}
        services[str(name)] = ServiceEntry(
            name=str(name),
            producer=str(meta["producer"]),
            consumers=_as_list(meta.get("consumers")),
            spec=str(meta.get("spec", "")),
            openapi=str(meta.get("openapi", "")),
            nota=str(meta.get("nota", "")),
        )
    callbacks = [
        Callback(
            name=str(c["name"]),
            notifier=str(c["notifier"]),
            receivers=_as_list(c.get("receivers")),
            method=str(c.get("method", "POST")).upper(),
            path=str(c["path"]),
            route=str(c.get("route", ROUTE_DIRECT)),
            nota=str(c.get("nota", "")),
        )
        for c in (doc.get("callbacks") or [])
    ]
    scp = None
    if doc.get("scp"):
        s = doc["scp"]
        scp = ScpModel(
            nf=str(s.get("nf", "scp")),
            model=str(s.get("model", "D")),
            direct_services=_as_list(s.get("direct_services")),
        )
    topo = Topology(
        namespace=str(doc.get("namespace", "5g-cp")),
        sbi_port=int(doc.get("sbi_port", 7777)),
        label_nf_name=str(labels.get("nf_name", "app.kubernetes.io/name")),
        label_namespace=str(labels.get("namespace", "io.kubernetes.pod.namespace")),
        identity_labels={str(k): str(v) for k, v in (labels.get("identity") or {}).items()},
        nfs=nfs,
        services=services,
        callbacks=callbacks,
        scp=scp,
        source_path=str(path),
    )
    validate(topo)
    return topo


def validate(topo: Topology) -> None:
    """Coherencia interna: toda NF citada existe y las rutas son válidas."""
    errors: list[str] = []
    known = set(topo.nfs)
    for s in topo.services.values():
        if s.producer not in known:
            errors.append(f"servicio {s.name}: productor desconocido '{s.producer}'")
        for c in s.consumers:
            if c not in known:
                errors.append(f"servicio {s.name}: consumidor desconocido '{c}'")
        if s.producer in s.consumers:
            errors.append(f"servicio {s.name}: el productor no puede consumirse a sí mismo")
    for cb in topo.callbacks:
        if cb.notifier not in known:
            errors.append(f"callback {cb.name}: notificador desconocido '{cb.notifier}'")
        for r in cb.receivers:
            if r not in known:
                errors.append(f"callback {cb.name}: receptor desconocido '{r}'")
        if cb.route not in (ROUTE_DIRECT, ROUTE_SCP):
            errors.append(f"callback {cb.name}: route debe ser 'direct' o 'scp'")
        if not cb.path.startswith("/"):
            errors.append(f"callback {cb.name}: el path debe empezar por '/'")
    if topo.scp is not None:
        if topo.scp.nf not in known:
            errors.append(f"scp.nf '{topo.scp.nf}' no está en 'nfs'")
        for s in topo.scp.direct_services:
            if s not in topo.services:
                errors.append(f"scp.direct_services: servicio desconocido '{s}'")
    if errors:
        raise ValueError("services.yaml inválido:\n  - " + "\n  - ".join(errors))

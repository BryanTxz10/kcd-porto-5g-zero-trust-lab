"""spec2policy: de la especificación 3GPP a la política de red (spec-as-policy).

Entradas: extractos OpenAPI 3GPP (Rel-17), tabla productor/consumidor por
servicio (TS 23.501 §7.2 / TS 23.502 §5.2) y flujos L7 de Hubble.
Salidas: CiliumNetworkPolicy con reglas http por método y path, y un informe
(Markdown + CSV) de lo que permite el estándar, lo observado y la diferencia.
"""

__version__ = "0.1.0"

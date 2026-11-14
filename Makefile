# Makefile — automatización de extremo a extremo del testbed CIB46.
# Objetivo: recrear el entorno y ejecutar el experimento con comandos cortos.
# Cada objetivo es idempotente (delega en los scripts de bootstrap/).

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---- Infraestructura (Ansible = recomendado; bash = respaldo) --------------
.PHONY: ansible-up
ansible-up: ## Despliega con Ansible (recomendado). Corre en ansible/
	cd ansible && ansible-playbook site.yml -K

.PHONY: up
up: ## Despliega con bash (respaldo): k3s -> Cilium -> ... -> C0
	bash bootstrap/bootstrap.sh

.PHONY: up-no-spire
up-no-spire: ## Igual que 'up' pero omite SPIRE (no afecta métricas C0-C3)
	bash bootstrap/bootstrap.sh --skip-spire

.PHONY: prereqs
prereqs: ## Verifica prerrequisitos del host
	bash bootstrap/00-prereqs.sh

# ---- Capas de política (demo) ----------------------------------------------
# Las transiciones imperativas por condición (transition-to-c*.sh) se archivaron
# en legacy/transitions/ (material de tesis, no mantenido). La forma soportada de
# aplicar cada capa de política es declarativa con Kustomize:
.PHONY: condition
condition: ## Aplica una capa de política con Kustomize (uso: make condition C=c1)
	kubectl delete ciliumnetworkpolicy -A -l cib46.io/managed=true 2>/dev/null || true
	kubectl kustomize --load-restrictor=LoadRestrictionsNone cilium-policies/conditions/$(C) | kubectl apply -f -
	kubectl get ciliumnetworkpolicies -A

# ---- Verificación (RM-01: plano de control, no ICMP) -----------------------
.PHONY: smoke
smoke: ## Prueba de humo: registro del UE + SBI desde sbi-probe (claro o mTLS)
	bash bootstrap/checks/smoke-control-plane.sh $(C)

# Modo de las políticas del lab: el de ansible/group_vars/all.yml salvo que
# se pase MODE=una-red|multus.
MODE ?= $(shell grep -qE '^deploy_multus:[[:space:]]*true' ansible/group_vars/all.yml && echo multus || echo una-red)$(shell grep -qE '^sbi_tls:[[:space:]]*true' ansible/group_vars/all.yml && echo -tls)

.PHONY: policies
policies: ## Aplica las políticas de Cilium del lab (MODE=una-red|multus[-tls]; por defecto, según deploy_multus y sbi_tls)
	kubectl apply -k cilium-policies/lab/$(MODE) --prune -l kcd.io/policy-set=lab \
	  --prune-allowlist=cilium.io/v2/CiliumNetworkPolicy
	kubectl get cnp -A -l kcd.io/policy-set=lab

.PHONY: demo-l7-ciega
demo-l7-ciega: ## Fase 4: la misma petición no autorizada al NRF (403 por L7 en claro; con mTLS, L7 ciega)
	bash bootstrap/checks/demo-l7-ciega.sh

.PHONY: demo-tetragon
demo-tetragon: ## Fase 6: abrir una shell en el AMF (Tetragon la mata) y ver el evento
	bash bootstrap/checks/demo-tetragon.sh

.PHONY: policy-matrix
policy-matrix: ## Matriz de flujos en los dos modos (una-red y multus), sin clúster (aproximación L3/L4)
	python3 bootstrap/checks/policy-matrix.py .

# Nota: el análisis estadístico de la tesis (ómnibus/post-hoc, tamaños de efecto)
# se archivó en legacy/analysis/ y ya no se expone como objetivo del Makefile.

# ---- Utilidades -------------------------------------------------------------
.PHONY: lint
lint: ## Chequeo de sintaxis de todos los scripts bash
	@for f in bootstrap/*.sh bootstrap/checks/*.sh \
	          attack-scripts/*.sh monitoring/*.sh helm-values/*.sh \
	          cilium-policies/c2/*.sh; do bash -n "$$f" && echo "ok  $$f"; done

.PHONY: kustomize-check
kustomize-check: ## Valida que los overlays Kustomize C0-C3 y las MultiNetworkPolicy construyan
	@for c in c0 c1 c2 c3; do \
	  echo "== build $$c =="; \
	  kustomize build --load-restrictor=LoadRestrictionsNone \
	    cilium-policies/conditions/$$c >/dev/null && echo "ok  $$c"; \
	done
	@for d in cilium-policies/lab/una-red cilium-policies/lab/multus cilium-policies/lab/una-red-tls cilium-policies/lab/multus-tls multinetwork-policies tetragon-policies; do \
	  echo "== build $$d =="; \
	  kustomize build $$d >/dev/null && echo "ok  $$d"; \
	done

.PHONY: ci
ci: ## Replica local del pipeline CI (lint bash + yaml + kustomize + python)
	@echo "== bash -n =="; $(MAKE) --no-print-directory lint
	@echo "== yamllint =="; yamllint -c .yamllint.yml .
	@echo "== kustomize =="; $(MAKE) --no-print-directory kustomize-check
	@echo "== python =="; python3 -m compileall -q attack-scripts bootstrap
	@echo "OK: validación local completa"

.PHONY: status
status: ## Estado rápido del testbed
	kubectl get nodes -o wide || true
	kubectl get pods -A -o wide | grep -E '5g-|cilium|multus|spire|metrics' || true
	kubectl get ciliumnetworkpolicies -A || true

.PHONY: subscribers
subscribers: ## Re-inserta el suscriptor (tras reinicio de MongoDB)
	bash helm-values/insert-subscribers.sh

.PHONY: ran-restart
ran-restart: ## Reinicia gNB y luego UE (tras reinicio del AMF)
	kubectl -n 5g-ran rollout restart deployment ueransim-gnb
	kubectl -n 5g-ran rollout status deployment ueransim-gnb --timeout=120s
	kubectl -n 5g-ran rollout restart deployment ueransim-ues
	kubectl -n 5g-ran rollout status deployment ueransim-ues --timeout=120s

.PHONY: help
help: ## Muestra esta ayuda
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | \
	 awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Fase 5 — spec-as-policy (tools/spec2policy, no necesita lab)
# ---------------------------------------------------------------------------
SPEC2POLICY_DIR := tools/spec2policy
SPEC2POLICY_PY  ?= python3

.PHONY: spec2policy
spec2policy: ## Fase 5: genera CNP L7 + blast radius map desde OpenAPI 3GPP y flujos Hubble de ejemplo
	cd $(SPEC2POLICY_DIR) && $(SPEC2POLICY_PY) -m spec2policy generate \
	  --openapi-dir data/openapi --services data/services.yaml \
	  --flows fixtures/hubble/sbi-sin-tls.jsonl --out examples/out --clean

.PHONY: spec2policy-test
spec2policy-test: ## Fase 5: ruff + pytest de tools/spec2policy
	cd $(SPEC2POLICY_DIR) && $(SPEC2POLICY_PY) -m ruff check . && \
	  $(SPEC2POLICY_PY) -m ruff format --check . && $(SPEC2POLICY_PY) -m pytest -q

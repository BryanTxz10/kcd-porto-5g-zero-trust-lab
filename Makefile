# Makefile — atajos del lab. Cada objetivo es idempotente.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---- Despliegue ---------------------------------------------------------------
.PHONY: up
up: ## Despliega el lab con Ansible (desde node-master)
	cd ansible && ansible-playbook site.yml -K

.PHONY: hardening
hardening: ## Pod Security Standards y taint del master (después de 'up')
	cd ansible && ansible-playbook hardening.yml -K

# ---- Verificación -------------------------------------------------------------
.PHONY: smoke
smoke: ## Prueba de humo: registro del UE + SBI desde sbi-probe (claro o mTLS)
	bash scripts/smoke-control-plane.sh $(C)

# Modo de las políticas del lab: el de ansible/group_vars/all.yml salvo que
# se pase MODE=una-red|multus.
MODE ?= $(shell grep -qE '^deploy_multus:[[:space:]]*true' ansible/group_vars/all.yml && echo multus || echo una-red)$(shell grep -qE '^sbi_tls:[[:space:]]*true' ansible/group_vars/all.yml && echo -tls)

.PHONY: policies
policies: ## Aplica las políticas de Cilium del lab (MODE=una-red|multus[-tls]; por defecto, según deploy_multus y sbi_tls)
	kubectl apply -k k8s/cilium/$(MODE) --prune -l kcd.io/policy-set=lab \
	  --prune-allowlist=cilium.io/v2/CiliumNetworkPolicy
	kubectl get cnp -A -l kcd.io/policy-set=lab

.PHONY: demo-l7-ciega
demo-l7-ciega: ## La misma petición no autorizada al NRF (403 por L7 en claro; con mTLS, L7 ciega)
	bash scripts/demo-l7-ciega.sh

.PHONY: demo-tetragon
demo-tetragon: ## Abre una shell en el AMF: Tetragon la mata y muestra el evento
	bash scripts/demo-tetragon.sh

.PHONY: policy-matrix
policy-matrix: ## Matriz de flujos en los dos modos (una-red y multus), sin clúster (aproximación L3/L4)
	python3 scripts/policy-matrix.py .

# ---- Utilidades -------------------------------------------------------------
.PHONY: lint
lint: ## Chequeo de sintaxis de todos los scripts bash
	@for f in scripts/*.sh attacks/*.sh k8s/helm-values/*.sh; do \
	  bash -n "$$f" || { echo "FAIL $$f"; exit 1; }; echo "ok  $$f"; done

.PHONY: kustomize-check
kustomize-check: ## Valida que construyan las políticas de Cilium, las MultiNetworkPolicy y Tetragon
	@for d in k8s/cilium/una-red k8s/cilium/multus k8s/cilium/una-red-tls k8s/cilium/multus-tls k8s/multinetwork k8s/tetragon; do \
	  kustomize build $$d >/dev/null || { echo "FAIL $$d"; exit 1; }; echo "ok  $$d"; \
	done

.PHONY: ci
ci: ## Replica local del pipeline CI (lint bash + yaml + kustomize + python)
	@echo "== bash -n =="; $(MAKE) --no-print-directory lint
	@echo "== yamllint =="; yamllint -c .yamllint.yml .
	@echo "== kustomize =="; $(MAKE) --no-print-directory kustomize-check
	@echo "== python =="; python3 -m compileall -q attacks scripts
	@echo "== policy-matrix =="; python3 scripts/policy-matrix.py . >/dev/null && echo "ok"
	@echo "OK: validación local completa"

.PHONY: status
status: ## Estado rápido del testbed
	kubectl get nodes -o wide || true
	kubectl get pods -A -o wide | grep -E '5g-|cilium|multus|kyverno|tetragon|metrics' || true
	kubectl get ciliumnetworkpolicies -A || true

.PHONY: subscribers
subscribers: ## Re-inserta el suscriptor (tras reinicio de MongoDB)
	bash k8s/helm-values/insert-subscribers.sh

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

# ---- spec-as-policy (tools/spec2policy, no necesita lab) ----------------------
SPEC2POLICY_DIR := tools/spec2policy
SPEC2POLICY_PY  ?= python3

.PHONY: spec2policy
spec2policy: ## Genera CNP L7 + blast radius map desde OpenAPI 3GPP y flujos Hubble de ejemplo
	cd $(SPEC2POLICY_DIR) && $(SPEC2POLICY_PY) -m spec2policy generate \
	  --openapi-dir data/openapi --services data/services.yaml \
	  --flows fixtures/hubble/sbi-sin-tls.jsonl --out examples/out --clean

.PHONY: spec2policy-test
spec2policy-test: ## ruff + pytest de tools/spec2policy
	cd $(SPEC2POLICY_DIR) && $(SPEC2POLICY_PY) -m ruff check . && \
	  $(SPEC2POLICY_PY) -m ruff format --check . && $(SPEC2POLICY_PY) -m pytest -q

# Observix Makefile (Windows Git Bash / macOS / Linux friendly)
# - Adds "doctor", "init", "fmt", "lint", "test", "clean"
# - Adds CP helpers + pipeline update helpers
# - Adds log tail helpers (auto-detects a logs dir if present)

SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c

# -------------------------
# Defaults (override at runtime)
# -------------------------
CP_URL ?= http://127.0.0.1:7000
REGION ?= eu-west-1

OBSERVIX ?= observix
OBSERVIX_AGENT ?= observix-agent
PY ?= python
PIP ?= pip

# Agent config paths
AGENT_A_CFG ?= config/agent.a.yaml
AGENT_B_CFG ?= config/agent.b.yaml

# Pipeline spec files (passed to "cp pipelines update --spec-file")
PIPE_A_SPEC ?= config/pipelines/pipeline-agent-a-indexed.json
PIPE_B_SPEC ?= config/pipelines/pipeline-agent-b-raw.json

# Pipeline IDs
PIPE_A_ID ?= 430974c9-3435-41ad-8f65-770ed365fb4a
PIPE_B_ID ?= 3090509d-e0d2-4c6b-b0a9-a2760cca7d4a

# Pipeline names
PIPE_A_NAME ?= syslog-5514-to-ec2-13-indexed
PIPE_B_NAME ?= syslog-5515-to-ec2-51-raw

# Agent IDs
AGENT_A_ID ?= agent-a
AGENT_B_ID ?= agent-b

# Optional logs directory (used by tail targets if you write logs to files later)
LOG_DIR ?= logs

# -------------------------
# Helpers
# -------------------------
define banner
	@printf "\n==> %s\n\n" "$(1)"
endef

.PHONY: help
help:
	@cat <<'EOF'
Observix Makefile targets

Setup / Hygiene
  make init                 Create common folders (config/pipelines, logs)
  make doctor               Validate CLI tools, configs, and CP health
  make clean                Remove common build/test caches

Python dev helpers (optional; uses whatever you already have installed)
  make fmt                  Format with ruff (if installed)
  make lint                 Lint with ruff (if installed)
  make test                 Run tests with pytest (if installed)

Agents
  make agent-a              Run agent-a with $(AGENT_A_CFG)
  make agent-b              Run agent-b with $(AGENT_B_CFG)

Control-plane
  make cp-health            GET /healthz
  make cp-agents            List agents
  make cp-pipelines         List pipelines
  make cp-assign-a          Get assignments for agent-a in $(REGION)
  make cp-assign-b          Get assignments for agent-b in $(REGION)

Pipelines (repeatable updates)
  make pipe-a-update        Update pipeline A using $(PIPE_A_SPEC)
  make pipe-b-update        Update pipeline B using $(PIPE_B_SPEC)

Convenience views
  make pipe-a-show          Print pipeline A from list output (best effort)
  make pipe-b-show          Print pipeline B from list output (best effort)

Log tails (if you use file destinations later)
  make tail-logs            Tail all files in $(LOG_DIR)

Overrides (examples)
  make CP_URL=http://127.0.0.1:7000 cp-health
  make REGION=eu-west-1 cp-assign-b
  make PIPE_B_ID=... PIPE_B_SPEC=... pipe-b-update
EOF

# -------------------------
# Setup / Hygiene
# -------------------------
.PHONY: init
init:
	$(call banner,Creating common folders)
	mkdir -p config/pipelines
	mkdir -p "$(LOG_DIR)"
	@echo "ok"

.PHONY: clean
clean:
	$(call banner,Cleaning caches)
	rm -rf .pytest_cache .ruff_cache .mypy_cache __pycache__ **/__pycache__ dist build *.egg-info 2>/dev/null || true
	@echo "ok"

# -------------------------
# Doctor (environment checks)
# -------------------------
.PHONY: doctor
doctor:
	$(call banner,Checking required CLIs)
	command -v "$(OBSERVIX)" >/dev/null 2>&1 || { echo "missing: $(OBSERVIX)"; exit 1; }
	command -v "$(OBSERVIX_AGENT)" >/dev/null 2>&1 || { echo "missing: $(OBSERVIX_AGENT)"; exit 1; }
	@echo "found: $(OBSERVIX)"
	@echo "found: $(OBSERVIX_AGENT)"

	$(call banner,Checking agent config files)
	test -f "$(AGENT_A_CFG)" || { echo "missing file: $(AGENT_A_CFG)"; exit 1; }
	test -f "$(AGENT_B_CFG)" || { echo "missing file: $(AGENT_B_CFG)"; exit 1; }
	@echo "ok: $(AGENT_A_CFG)"
	@echo "ok: $(AGENT_B_CFG)"

	$(call banner,Checking pipeline spec files (for update targets))
	test -f "$(PIPE_A_SPEC)" || echo "warn: missing file: $(PIPE_A_SPEC) (pipe-a-update will fail until created)"
	test -f "$(PIPE_B_SPEC)" || echo "warn: missing file: $(PIPE_B_SPEC) (pipe-b-update will fail until created)"

	$(call banner,Checking control-plane health)
	# If CP is down, fail with a clear message
	if ! "$(OBSERVIX)" cp health --url "$(CP_URL)" >/dev/null 2>&1; then \
	  echo "control-plane not reachable at $(CP_URL)"; \
	  echo "tip: export OBSERVIX_CP_URL or run: make CP_URL=... cp-health"; \
	  exit 1; \
	fi
	@echo "ok: control-plane healthy at $(CP_URL)"

# -------------------------
# Python helpers (optional)
# -------------------------
.PHONY: fmt lint test
fmt:
	$(call banner,Formatting (ruff))
	if command -v ruff >/dev/null 2>&1; then \
	  ruff format . ; \
	else \
	  echo "ruff not installed; skipping. install: pip install ruff"; \
	fi

lint:
	$(call banner,Linting (ruff))
	if command -v ruff >/dev/null 2>&1; then \
	  ruff check . ; \
	else \
	  echo "ruff not installed; skipping. install: pip install ruff"; \
	fi

test:
	$(call banner,Tests (pytest))
	if command -v pytest >/dev/null 2>&1; then \
	  pytest -q ; \
	else \
	  echo "pytest not installed; skipping. install: pip install pytest"; \
	fi

# -------------------------
# Agents
# -------------------------
.PHONY: agent-a agent-b
agent-a:
	$(call banner,Running agent-a)
	"$(OBSERVIX_AGENT)" -c "$(AGENT_A_CFG)"

agent-b:
	$(call banner,Running agent-b)
	"$(OBSERVIX_AGENT)" -c "$(AGENT_B_CFG)"

# -------------------------
# Control-plane operations
# -------------------------
.PHONY: cp-health cp-agents cp-pipelines cp-assign-a cp-assign-b
cp-health:
	$(call banner,CP health)
	"$(OBSERVIX)" cp health --url "$(CP_URL)"

cp-agents:
	$(call banner,CP agents)
	"$(OBSERVIX)" cp agents --url "$(CP_URL)"

cp-pipelines:
	$(call banner,CP pipelines list)
	"$(OBSERVIX)" cp pipelines list --url "$(CP_URL)"

cp-assign-a:
	$(call banner,CP assignments get (agent-a))
	"$(OBSERVIX)" cp assignments get --agent-id "$(AGENT_A_ID)" --region "$(REGION)" --url "$(CP_URL)"

cp-assign-b:
	$(call banner,CP assignments get (agent-b))
	"$(OBSERVIX)" cp assignments get --agent-id "$(AGENT_B_ID)" --region "$(REGION)" --url "$(CP_URL)"

# -------------------------
# Pipeline updates
# -------------------------
.PHONY: pipe-a-update pipe-b-update
pipe-a-update:
	$(call banner,Updating pipeline A)
	test -f "$(PIPE_A_SPEC)" || { echo "missing spec file: $(PIPE_A_SPEC)"; exit 1; }
	"$(OBSERVIX)" cp pipelines update \
	  --pipeline-id "$(PIPE_A_ID)" \
	  --name "$(PIPE_A_NAME)" \
	  --enabled \
	  --spec-file "$(PIPE_A_SPEC)" \
	  --url "$(CP_URL)"

pipe-b-update:
	$(call banner,Updating pipeline B)
	test -f "$(PIPE_B_SPEC)" || { echo "missing spec file: $(PIPE_B_SPEC)"; exit 1; }
	"$(OBSERVIX)" cp pipelines update \
	  --pipeline-id "$(PIPE_B_ID)" \
	  --name "$(PIPE_B_NAME)" \
	  --enabled \
	  --spec-file "$(PIPE_B_SPEC)" \
	  --url "$(CP_URL)"

# -------------------------
# Convenience "show"
# -------------------------
.PHONY: pipe-a-show pipe-b-show
pipe-a-show:
	$(call banner,Showing pipeline A)
	"$(OBSERVIX)" cp pipelines list --url "$(CP_URL)" | sed -n '/"pipeline_id": "$(PIPE_A_ID)"/,/^    }/p' || true

pipe-b-show:
	$(call banner,Showing pipeline B)
	"$(OBSERVIX)" cp pipelines list --url "$(CP_URL)" | sed -n '/"pipeline_id": "$(PIPE_B_ID)"/,/^    }/p' || true

# -------------------------
# Log tail helpers (optional)
# -------------------------
.PHONY: tail-logs
tail-logs:
	$(call banner,Tailing logs in $(LOG_DIR))
	mkdir -p "$(LOG_DIR)"
	# Tail all files in LOG_DIR (best effort). If none exist, keep waiting.
	if ls -1 "$(LOG_DIR)"/* >/dev/null 2>&1; then \
	  tail -n 200 -F "$(LOG_DIR)"/* ; \
	else \
	  echo "no log files found in $(LOG_DIR) yet"; \
	  echo "tip: if you use FileDestination later, set its path under $(LOG_DIR)"; \
	  while true; do sleep 2; done; \
	fi

#!/usr/bin/env bash
# Nightly/deep tier: proof obligations + Event-B/ProB + Z3 (+ AI review of any residual
# findings, if DEEPSEEK_API_KEY is set) — the non-semgrep, non-Joern, non-test slice of
# `stateguard run-cycle`. Review units are intentionally left for real human claim/
# complete (--no-auto-complete-review): unlike the order-workflow demo, CI must never
# auto-rubber-stamp review. Doctor is run non-strict here; call `stateguard doctor
# --strict` as its own separate CI step where a hard gate is wanted.
set -euo pipefail
REPO_ROOT=${1:-$(pwd)}
REPO_ROOT=$(cd -- "$REPO_ROOT" && pwd)

stateguard --repo "$REPO_ROOT" run-cycle \
  --skip semgrep,joern,tests \
  --no-auto-complete-review \
  --no-strict-doctor

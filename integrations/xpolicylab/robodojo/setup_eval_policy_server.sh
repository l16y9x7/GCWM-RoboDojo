#!/bin/bash
set -euo pipefail

bench_name=${1}
task_name=${2}
ckpt_name=${3}
env_cfg_type=${4}
action_type=${5}
seed=${6}
policy_gpu_id=${7}
policy_conda_env=${8}
policy_server_port=${9}
policy_server_host=${10:-"localhost"}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
XPL_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BENCH_ROOT="$(cd "${XPL_ROOT}/.." && pwd)"
UTILS_DIR="${XPL_ROOT}/utils"

# The model's endpoint and name: from the environment, or from an env file next to this script
# (ROBODOJO_ENV_FILE) that keeps credentials out of the repository.
ROBODOJO_ENV_FILE="${ROBODOJO_ENV_FILE:-${SCRIPT_DIR}/.env}"
if [[ -f "${ROBODOJO_ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ROBODOJO_ENV_FILE}"
    set +a
fi

export ROBODOJO_MODEL="${ROBODOJO_MODEL:-}"
export ROBODOJO_BASE_URL="${ROBODOJO_BASE_URL:-${OPENAI_BASE_URL:-}}"
if [[ -z "${ROBODOJO_API_KEY_ENV:-}" && -n "${OPENAI_API_KEY:-}" ]]; then
    export ROBODOJO_API_KEY_ENV=OPENAI_API_KEY
fi

if [[ -z "${ROBODOJO_MODEL}" || -z "${ROBODOJO_BASE_URL}" ]]; then
    echo "[SERVER] missing model settings; set ROBODOJO_MODEL/ROBODOJO_BASE_URL or provide ${ROBODOJO_ENV_FILE}" >&2
    exit 1
fi

policy_name="$(basename "${SCRIPT_DIR}")"
yaml_file="${XPL_ROOT}/policy/${policy_name}/deploy.yml"

echo "[SERVER] policy=${policy_name}, task=${task_name}, policy_server_port=${policy_server_port}"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${policy_conda_env}"

# SAM3's checkpoint: where download_assets.sh puts it, unless the caller names another.
if [[ -z "${SAM3_CHECKPOINT_PATH:-}" && -f "${SCRIPT_DIR}/checkpoints/sam3.pt" ]]; then
    export SAM3_CHECKPOINT_PATH="${SCRIPT_DIR}/checkpoints/sam3.pt"
fi

# BENCH_ROOT on the path: `XPolicyLab.policy.robodojo` resolves whether or not XPolicyLab
# was pip-installed into this environment.
exec env \
    PYTHONUNBUFFERED=1 \
    PYTHONWARNINGS=ignore::UserWarning \
    PYTHONPATH="${BENCH_ROOT}${PYTHONPATH:+:${PYTHONPATH}}" \
    CUDA_VISIBLE_DEVICES="${policy_gpu_id}" \
    python "${XPL_ROOT}/setup_policy_server.py" \
        --config_path "${yaml_file}" \
        --overrides \
            port="${policy_server_port}" \
            host="${policy_server_host}" \
            bench_name="${bench_name}" \
            task_name="${task_name}" \
            ckpt_name="${ckpt_name}" \
            env_cfg_type="${env_cfg_type}" \
            seed="${seed}" \
            policy_name="${policy_name}" \
            action_type="${action_type}"

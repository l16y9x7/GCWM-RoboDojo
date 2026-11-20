#!/bin/bash
# The policy environment of roboskylar: XPolicyLab's policy server, this package, and SAM3,
# the one model the policy side loads.  Run it inside the environment the policy server will
# use (<policy_env> of eval.sh), from this directory once it lives at
# XPolicyLab/policy/roboskylar.  That environment needs a CUDA build of torch and the
# torchvision that goes with it first: this script installs neither, and keeps both as they are.
#
#   bash install.sh [<roboskylar checkout>]
#
# Without an argument the package is installed from the checkout this directory is linked from
# (integrations/xpolicylab/roboskylar of a roboskylar checkout).  The simulator's environment
# needs nothing beyond RoboDojo's own installation.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
XPL_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CHECKOUT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../../.." && pwd)"
if [[ -f "${CHECKOUT}/src/roboskylar/__init__.py" ]]; then
    DEFAULT_SOURCE="${CHECKOUT}"
else
    DEFAULT_SOURCE=""
fi
ROBOSKYLAR_SOURCE="${1:-${ROBOSKYLAR_SOURCE:-${DEFAULT_SOURCE}}}"
if [[ -z "${ROBOSKYLAR_SOURCE}" ]]; then
    echo "[install] roboskylar checkout not found. Pass it: bash install.sh /path/to/roboskylar" >&2
    exit 1
fi
# The revision of the sam3 package the masks were measured with.
SAM3_SOURCE="${SAM3_SOURCE:-git+https://github.com/RLinf/sam3.git@c1f6b1e83967c912f675d8975d437ccdc41e17d8}"

if ! python -c "import torch, torchvision, sys; sys.exit(0 if torch.cuda.is_available() else 1)"; then
    echo "[install] this environment needs a CUDA build of torch, and the torchvision built for it," >&2
    echo "[install] before SAM3 can load (see https://pytorch.org/get-started/locally/)" >&2
    exit 1
fi

# pip must leave that torch alone: SAM3's requirements would otherwise pull in the newest torch
# and torchvision, built for whatever CUDA is current.  SAM3 also needs numpy 1.x, and with it
# the last OpenCV line that still supports numpy 1.x.
constraints="$(mktemp)"
trap 'rm -f "${constraints}"' EXIT
python - > "${constraints}" <<'PY'
import importlib.metadata as md

for name in ("torch", "torchvision"):
    print(f"{name}=={md.version(name)}")
print("numpy>=1.26,<2")
print("opencv-python-headless<4.12")
PY
pip_install() { python -m pip install -c "${constraints}" "$@"; }

# XPolicyLab itself: the websocket policy server and the image decoding it does.
pip_install -e "${XPL_ROOT}"
if [[ -d "${ROBOSKYLAR_SOURCE}" ]]; then
    pip_install -e "${ROBOSKYLAR_SOURCE}"
else
    pip_install "roboskylar @ ${ROBOSKYLAR_SOURCE}"
fi
# What the episode driver imports (the package declares no dependencies of its own).
pip_install "numpy" "pillow" "pyyaml>=6" "httpx>=0.27" "mcp>=1.8,<2" "uvicorn"
# SAM3, and what its image model imports without declaring it.
pip_install "sam3 @ ${SAM3_SOURCE}" "einops" "pycocotools" "psutil"

python - <<'PY'
import torch
from sam3.model.sam3_image_processor import Sam3Processor  # noqa: F401
from sam3.model_builder import build_sam3_image_model  # noqa: F401

import roboskylar.robots

roboskylar.robots.get_adapter("robodojo_xpl_rgb").host_module()
print(f"[install] torch {torch.__version__}, SAM3 and roboskylar import")
PY

echo "[install] done.  SAM3's checkpoint: bash ${SCRIPT_DIR}/download_assets.sh"

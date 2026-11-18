#!/usr/bin/env bash
set -euo pipefail
python -m zipfile -e FlyBrain_Research_Platform_Fresh_Install_v0.14.0.zip .release
python scripts/apply_chat_bridge.py --source .release/FlyBrain_Research_Platform_v0.14.0
python -m pip install -e .release/FlyBrain_Research_Platform_v0.14.0/components/FlyBrain-NOS

#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

python3 V24_3_NIGHTLY_REPORT.py
echo
python3 V24_3_RISK_BASKET_REPORT.py

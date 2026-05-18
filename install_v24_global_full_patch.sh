#!/usr/bin/env bash
set -e
cd /home/philippe_vacher06/bot-pivot/live
source venv/bin/activate

echo "1) Audit avant patch"
python audit_v24_global_state.py || true

echo
echo "2) Patch exécution LIMIT/STOP/broker"
python patch_v24_global_execution.py

echo
echo "3) Patch cadence/cache + lanceur SCALP ACTIVE"
python patch_v24_cadence_cache.py

echo
echo "4) Patch runner guard marge/sélection"
python patch_runner_insert_scalp_guard.py

echo
echo "5) Vérification"
bash check_v24_global_patch.sh

echo
echo "6) Audit après patch"
python audit_v24_global_state.py

echo
echo "INSTALLATION GLOBALE TERMINÉE"

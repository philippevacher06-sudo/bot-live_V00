# BOT_PIVOT_07_main.py
# Module 07A — orchestrateur simple en DRY_RUN
# Lance une seule séquence :
# 03 ticks -> 04 signal tick -> 05 cycle engine
# Aucun ordre réel.

import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import BOT_PIVOT_00_config as CFG

LOG_DIR = CFG.LOG_DIR

def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def run_step(name, cmd, log_file):
    print()
    print("=" * 120)
    print(f"07A — {name}")
    print("=" * 120)
    print("Commande :", " ".join(cmd))
    print("-" * 120)

    with open(log_file, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 120 + "\n")
        f.write(f"{utc_now()} — {name}\n")
        f.write("CMD: " + " ".join(cmd) + "\n")
        f.write("=" * 120 + "\n")

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        print(result.stdout)
        f.write(result.stdout)
        f.write(f"\nRETURN_CODE={result.returncode}\n")

    if result.returncode != 0:
        raise RuntimeError(f"Étape échouée : {name}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tick-seconds", type=int, default=45)
    parser.add_argument("--print-every", type=int, default=15)
    parser.add_argument("--min-spread-samples", type=int, default=20)
    parser.add_argument("--assets", default="ALL")
    parser.add_argument("--skip-ticks", action="store_true")
    parser.add_argument("--with-execution", action="store_true", help="Ajoute 06F plan-open en DRY_RUN")
    args = parser.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"orchestrator_07A_{stamp}.log"

    print()
    print("=" * 120)
    print("BOT_PIVOT_07A — ORCHESTRATEUR DRY_RUN")
    print("=" * 120)
    print("Mode        : DRY_RUN")
    print("Ordres réels : NON")
    print("Log         :", log_file)
    print("=" * 120)

    if not args.skip_ticks:
        run_step(
            "MODULE 03 — TICKS WEBSOCKET",
            [
                "python",
                "BOT_PIVOT_03_tick_stream.py",
                "--seconds",
                str(args.tick_seconds),
                "--print-every",
                str(args.print_every),
            ],
            log_file,
        )

    run_step(
        "MODULE 04 — SIGNAUX TICK",
        [
            "python",
            "BOT_PIVOT_04_signal_tick.py",
            "--min-spread-samples",
            str(args.min_spread_samples),
        ],
        log_file,
    )

    cmd05 = ["python", "BOT_PIVOT_05_cycle_engine.py"]
    if args.assets != "ALL":
        cmd05 += ["--assets", args.assets]

    run_step(
        "MODULE 05 — CYCLE ENGINE",
        cmd05,
        log_file,
    )

    if args.with_execution:
        cmd06 = [
            "python",
            "BOT_PIVOT_06F_execution.py",
            "--mode",
            "plan-open",
            "--assets",
            args.assets,
        ]

        run_step(
            "MODULE 06F — EXECUTION PLAN DRY_RUN",
            cmd06,
            log_file,
        )

    print()
    print("=" * 120)
    print("07A TERMINÉ")
    print("=" * 120)
    print("Le cycle ticks → signaux → moteur cycle a été exécuté.")
    if args.with_execution:
        print("Le plan d'exécution 06F a aussi été testé en DRY_RUN.")
    print("Aucun ordre réel n'a été envoyé.")
    print("Log :", log_file)
    print("=" * 120)

if __name__ == "__main__":
    main()

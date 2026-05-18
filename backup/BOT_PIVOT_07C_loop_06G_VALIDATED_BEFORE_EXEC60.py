# BOT_PIVOT_07C_loop.py
# Boucle continue BOT-PIVOT en DRY_RUN
# Aucun ordre réel.
# 03 ticks -> 04 signaux -> 05 cycle engine
# 06F plan-open DRY_RUN seulement toutes les X secondes.

import argparse
import subprocess
import time
from datetime import datetime, timezone

import BOT_PIVOT_00_config as CFG

LOG_DIR = CFG.LOG_DIR

def utc():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def run_cmd(title, cmd, log_file):
    print()
    print("=" * 120)
    print(title)
    print("=" * 120)
    print("CMD :", " ".join(cmd))
    print("-" * 120)

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    print(result.stdout)

    with open(log_file, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 120 + "\n")
        f.write(f"{utc()} — {title}\n")
        f.write("CMD: " + " ".join(cmd) + "\n")
        f.write(result.stdout)
        f.write(f"\nRETURN_CODE={result.returncode}\n")

    return result.returncode

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=3, help="Nombre de cycles de test")
    parser.add_argument("--forever", action="store_true", help="Boucle infinie")
    parser.add_argument("--tick-seconds", type=int, default=45)
    parser.add_argument("--print-every", type=int, default=15)
    parser.add_argument("--pause", type=int, default=15)
    parser.add_argument("--exec-every", type=int, default=120, help="Secondes entre deux appels 06F")
    args = parser.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"orchestrator_07C_loop_{stamp}.log"

    print()
    print("=" * 120)
    print("BOT_PIVOT_07C — BOUCLE DRY_RUN")
    print("=" * 120)
    print("Ordres réels       : NON")
    print("SEND_REAL_ORDERS   : False dans 06F")
    print("Cycles test        :", "infini" if args.forever else args.cycles)
    print("Ticks secondes     :", args.tick_seconds)
    print("Pause              :", args.pause, "sec")
    print("06G toutes les     :", args.exec_every, "sec")
    print("Log                :", log_file)
    print("=" * 120)

    last_exec_ts = 0
    i = 0

    while True:
        i += 1

        print()
        print("#" * 120)
        print(f"BOUCLE 07C — CYCLE {i} — {utc()}")
        print("#" * 120)

        rc = run_cmd(
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
        if rc != 0:
            print("ERREUR module 03. Arrêt boucle.")
            break

        rc = run_cmd(
            "MODULE 04 — SIGNAUX TICK",
            [
                "python",
                "BOT_PIVOT_04_signal_tick.py",
                "--min-spread-samples",
                "20",
            ],
            log_file,
        )
        if rc != 0:
            print("ERREUR module 04. Arrêt boucle.")
            break

        rc = run_cmd(
            "MODULE 05 — CYCLE ENGINE",
            ["python", "BOT_PIVOT_05_cycle_engine.py"],
            log_file,
        )
        if rc != 0:
            print("ERREUR module 05. Arrêt boucle.")
            break

        now = time.time()

        if now - last_exec_ts >= args.exec_every:
            rc = run_cmd(
                "MODULE 06G — EXECUTION DEPUIS CYCLE_STATE DRY_RUN",
                [
                    "python",
                    "BOT_PIVOT_06G_execution_from_cycle_state.py",
                    "--mode",
                    "plan",
                    "--assets",
                    "ALL",
                ],
                log_file,
            )
            last_exec_ts = now

            if rc != 0:
                print("ERREUR module 06G. Arrêt boucle.")
                break
        else:
            remain = args.exec_every - (now - last_exec_ts)
            print()
            print("=" * 120)
            print(f"MODULE 06G — SKIP anti-429 — prochain appel dans environ {remain:.0f}s")
            print("=" * 120)

        if not args.forever and i >= args.cycles:
            print()
            print("=" * 120)
            print("07C TERMINÉ — nombre de cycles atteint")
            print("=" * 120)
            break

        print()
        print("=" * 120)
        print(f"Pause {args.pause}s avant prochain cycle")
        print("=" * 120)
        time.sleep(args.pause)

    print()
    print("=" * 120)
    print("FIN BOT_PIVOT_07C")
    print("Aucun ordre réel n'a été envoyé.")
    print("Log :", log_file)
    print("=" * 120)

if __name__ == "__main__":
    main()

import argparse
import json
import sys

from .config import Settings


def doctor():
    settings = Settings.load()
    result = settings.public_status()
    result["database_connection"] = "not_configured"
    if settings.host and (settings.password or settings.host in {"localhost", "127.0.0.1", "::1"}):
        try:
            from .memory import Memory
            result["database_connection"] = "verified" if Memory(settings).probe() else "failed"
        except Exception as exc:
            # Exception text can contain credentials/URLs. Report only class, not text.
            result["database_connection"] = "failed"
            result["error_type"] = type(exc).__name__
    print(json.dumps(result, indent=2))
    return 0 if result["database_connection"] == "verified" else 2


def main():
    parser = argparse.ArgumentParser(prog="swarmlab")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Verify configuration and a real FalkorDB write/read round trip")
    commands.add_parser("world-check", help="Run a deterministic local engine check; no model or database")
    serve = commands.add_parser("serve", help="Start the local API")
    serve.add_argument("--port", type=int, default=8000)
    discover = commands.add_parser("discover", help="Run model-driven discovery")
    discover.add_argument("--seed", type=int, default=11)
    sleep = commands.add_parser("sleep", help="Prepare memory from a completed discovery episode")
    sleep.add_argument("--episode", required=True)
    transfer = commands.add_parser("transfer", help="Run a fresh-context evaluation")
    transfer.add_argument("--artifact", default="")
    transfer.add_argument("--seed", type=int, default=101)
    transfer.add_argument("--condition", choices=["none", "raw", "sleep", "flat", "local_rule"], default="sleep")
    evaluate_parser = commands.add_parser("evaluate", help="Run paired memory comparisons and export JSON/CSV")
    evaluate_parser.add_argument("--artifact", required=True)
    evaluate_parser.add_argument("--seeds", type=int, nargs="+", default=[101, 102, 103])
    args = parser.parse_args()
    if args.command == "doctor":
        sys.exit(doctor())
    if args.command == "world-check":
        from .world import World
        world = World.create(11)
        print(json.dumps({"mode": "engine_check", "observation": world.observe("a")}, indent=2))
    elif args.command == "serve":
        import uvicorn
        uvicorn.run("swarmlab.server:app", host="127.0.0.1", port=args.port)
    elif args.command in {"discover", "sleep", "transfer", "evaluate"}:
        from .memory import Memory
        from .model import create_model
        from .awake import run_awake
        from .sleep import run_sleep
        from .experiment import save_run, transfer, evaluate
        settings = Settings.load()
        try:
            model = create_model(settings)
            memory = Memory(settings)
            if args.command == "evaluate":
                print(json.dumps(evaluate(memory, model, artifact_id=args.artifact, seeds=args.seeds), indent=2))
            elif args.command == "sleep":
                print(json.dumps(run_sleep(memory, model, args.episode), indent=2))
            else:
                run = (run_awake(memory, model, seed=args.seed) if args.command == "discover"
                       else transfer(memory, model, artifact_id=args.artifact, seed=args.seed, condition=args.condition))
                print(json.dumps({"result": run["result"], "saved": save_run(run)}, indent=2))
        except Exception as exc:
            print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                              "next_step": "Run doctor and check local configuration. No simulated fallback was used."}))
            sys.exit(1)



if __name__ == "__main__":
    main()

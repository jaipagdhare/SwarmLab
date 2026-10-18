"""One local job at a time; persisted job reports support labeled replay."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import RLock, Event
from datetime import datetime, timezone
import json

from .config import ROOT, Settings
from .memory import Memory, new_id
from .model import create_model
from .awake import Budget, run_awake
from .sleep import run_sleep
from .experiment import transfer, evaluate, save_run


class Jobs:
    def __init__(self):
        self.lock = RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="swarmlab")
        self.records = {}
        self.stops = {}

    def busy(self):
        with self.lock:
            return any(job["status"] in {"queued", "running"} for job in self.records.values())

    def start(self, action, params):
        settings = Settings.load()
        if not action.startswith("local_"):
            create_model(settings)
        if not settings.host:
            raise ValueError("Database host missing")
        with self.lock:
            if self.busy():
                raise RuntimeError("A run is already active")
            job_id = new_id("job")
            self.records[job_id] = {"id": job_id, "action": action, "params": params,
                                   "status": "queued", "created_at": datetime.now(timezone.utc).isoformat(),
                                   "events": [], "latest_snapshot": None, "result": None}
            self.stops[job_id] = Event()
            self.executor.submit(self._run, job_id, settings)
            return self.get(job_id)

    def get(self, job_id):
        with self.lock:
            if job_id not in self.records:
                raise KeyError("Unknown job")
            return deepcopy(self.records[job_id])

    def list(self):
        with self.lock:
            return [{k: deepcopy(v) for k, v in job.items() if k not in {"events", "latest_snapshot", "result"}}
                    for job in reversed(list(self.records.values()))]

    def cancel(self, job_id):
        with self.lock:
            if job_id not in self.stops:
                raise KeyError("Unknown job")
            self.stops[job_id].set()
            return {"status": "cancellation_requested", "note": "The in-flight provider request may finish first."}

    def _update(self, job_id, **values):
        with self.lock:
            self.records[job_id].update(values)

    def _step(self, job_id, data):
        with self.lock:
            job = self.records[job_id]
            job["events"].append({"episode_id": data["episode_id"], **data["event"]})
            job["events"] = job["events"][-120:]
            job["latest_snapshot"] = data["evaluator_snapshot"]

    def _run(self, job_id, settings):
        job = self.get(job_id)
        params, action = job["params"], job["action"]
        self._update(job_id, status="running", started_at=datetime.now(timezone.utc).isoformat())
        try:
            memory = Memory(settings)
            model = None if action.startswith("local_") else create_model(settings)
            memory.save_job(self.get(job_id))
            budget = Budget(max_actions=params.get("max_actions", 40), max_calls=params.get("max_actions", 40),
                            max_seconds=params.get("max_seconds", 600))
            cancelled = self.stops[job_id].is_set
            if model is not None and settings.model_provider == "gemini":
                model.cancelled = cancelled
                model.on_wait = lambda delay: self._update(job_id, rate_wait_seconds=round(delay, 1))
            on_step = lambda data: self._step(job_id, data)
            if action in {"local_learn", "local_transfer", "local_audit"}:
                from .local_runner import run_local
                if action in {"local_learn", "local_audit"}:
                    for episode in memory.list_episodes():
                        if cancelled(): break
                        if episode['status'] != 'running': memory.ingest_local_episode(episode['id'])
                    rule = memory.refresh_local_rule()
                if action == "local_audit":
                    result = {"local_rule":rule, "model_calls":0}
                else:
                    result = run_local(memory, mode='learn' if action=='local_learn' else 'transfer',
                                       seed=params.get('seed',11),max_actions=params.get('max_actions',250),
                                       on_step=on_step,cancelled=cancelled)
            elif action == "incident":
                from .incident import IncidentStore, run_incident
                result = run_incident(IncidentStore(memory), model, params['lab_id'], params.get('mode','pilot'),
                                      cancelled=cancelled, progress=lambda value:self._update(job_id,incident_progress=value))
            elif action == "discover":
                result = run_awake(memory, model, seed=params.get("seed", 11), budget=budget,
                                   on_step=on_step, cancelled=cancelled)
                save_run(result)
            elif action == "sleep":
                result = run_sleep(memory, model, params["episode_id"])
            elif action == "transfer":
                result = transfer(memory, model, artifact_id=params["artifact_id"], seed=params.get("seed", 101),
                                  condition=params.get("condition", "sleep"), budget=budget,
                                  on_step=on_step, cancelled=cancelled)
                save_run(result)
            elif action == "evaluate":
                result = evaluate(memory, model, artifact_id=params["artifact_id"], seeds=params.get("seeds", [101, 102, 103]),
                                  conditions=params.get("conditions", ["none", "raw", "sleep"]), budget=budget,
                                  on_step=on_step, cancelled=cancelled)
            else:
                raise ValueError("Unknown operation")
            self._update(job_id, result=result, status="cancelled" if cancelled() else "complete")
        except Exception as exc:
            self._update(job_id, status="failed", error={"type": type(exc).__name__,
                         "code": getattr(exc, "code", "operation_failed"), "usage": getattr(exc, "usage", None),
                         "validation_errors": getattr(exc, "validation_errors", None),
                         "note": str(exc) if (action.startswith("local_") or action == "incident") and isinstance(exc, ValueError) else "Sleep output failed validation; inspect the listed fields and retry preparation." if getattr(exc, "code", "") == "invalid_sleep_artifact" else "Check connections and input IDs. No fallback result was generated."})
        finally:
            self._update(job_id, finished_at=datetime.now(timezone.utc).isoformat(), rate_wait_seconds=0)
            try:
                Memory(settings).save_job(self.get(job_id))
            except Exception as exc:
                self._update(job_id, persistence_error=type(exc).__name__)
            directory = ROOT / "outputs" / "runs"
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f"{job_id}.json").write_text(json.dumps(self.get(job_id), indent=2), encoding="utf-8")

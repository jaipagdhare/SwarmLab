from typing import Literal
from urllib.parse import urlparse
import json
import re

from dotenv import set_key
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field, SecretStr
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import ROOT, Settings
from .memory import Memory
from .model import create_model
from .jobs import Jobs
from .schemas import StrictModel

app = FastAPI(title="SwarmLab", version="0.1.0")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
jobs = Jobs()
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    # Validation errors can contain the original credential input.
    return JSONResponse({"detail": [{"loc": e["loc"], "type": e["type"], "msg": e["msg"]}
                                    for e in exc.errors()]}, status_code=422)


@app.get("/api/world-preview")
def world_preview(seed: int = Query(default=11, ge=0, le=2147483647)):
    from .world import World
    return World.create(seed).evaluator_snapshot()


@app.middleware("http")
async def same_origin(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and urlparse(origin).netloc != request.headers.get("host"):
        return JSONResponse({"detail": "Cross-origin access is not allowed"}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    return response


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/health")
def health():
    return {"status": "running", "database_verified": False,
            "note": "Use Check connections for an authenticated database check."}


@app.get("/api/config-status")
def config_status():
    settings = Settings.load()
    return {**settings.public_status(), "database_host": settings.host, "database_port": settings.port,
            "database_username": settings.username}


class ConnectionConfig(StrictModel):
    host: str = Field(min_length=1, max_length=250, pattern=r"^[A-Za-z0-9.-]+$")
    port: int = Field(ge=1, le=65535)
    username: str = Field(default="", max_length=100)
    tls: bool
    password: SecretStr | None = None
    api_key: SecretStr | None = None


@app.post("/api/config")
def save_config(payload: ConnectionConfig):
    if jobs.busy():
        raise HTTPException(409, "Wait for the active run before changing connections")
    values = {"FALKORDB_HOST": payload.host, "FALKORDB_PORT": str(payload.port),
              "FALKORDB_USERNAME": payload.username, "FALKORDB_TLS": str(payload.tls).lower(),
              "MODEL_PROVIDER": "gemini", "MODEL_NAME": "gemini-3.5-flash-lite"}
    if payload.password and payload.password.get_secret_value().strip():
        values["FALKORDB_PASSWORD"] = payload.password.get_secret_value().strip()
    if payload.api_key and payload.api_key.get_secret_value().strip():
        values["GEMINI_API_KEY"] = payload.api_key.get_secret_value().strip()
    for key, value in values.items():
        set_key(ROOT / ".env", key, value)
    return {"status": "saved", "credentials_returned": False}


@app.post("/api/check-connections")
def check_connections():
    if jobs.busy():
        raise HTTPException(409, "A run is active")
    settings = Settings.load()
    result = {"database": "not_configured", "model": "not_configured"}
    if settings.host:
        try:
            result["database"] = "verified" if Memory(settings).probe() else "failed"
        except Exception as exc:
            result.update(database="failed", database_error=type(exc).__name__)
    if settings.model_api_key:
        try:
            response = create_model(settings).complete(
                system="Return ok=true to confirm this connection.", context={},
                schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False},
                max_output_tokens=512, timeout_seconds=150)
            result["model"] = "verified" if response.value.get("ok") is True else "failed"
            result["model_usage"] = response.usage
        except Exception as exc:
            result.update(model="failed", model_error=getattr(exc, "code", type(exc).__name__))
    return result


@app.get("/api/local-rule")
def local_rule():
    try:
        return {"local_rule":Memory(Settings.load()).get_local_rule()}
    except Exception:
        raise HTTPException(503, "Cannot read local learning state from FalkorDB") from None


@app.get("/api/episodes")
def episodes():
    try:
        return {"episodes": Memory(Settings.load()).list_episodes()}
    except Exception as exc:
        raise HTTPException(503, {"status": "database_unavailable", "error_type": type(exc).__name__}) from None


@app.get("/api/artifacts")
def artifacts():
    try:
        return {"artifacts": Memory(Settings.load()).list_artifacts()}
    except Exception:
        raise HTTPException(503, "Cannot load prepared memories from FalkorDB") from None


@app.get("/api/artifacts/{artifact_id}")
def artifact(artifact_id: str):
    try:
        memory = Memory(Settings.load())
        return {**memory.get_artifact(artifact_id), "graph": memory.retrieve_procedures_with_evidence(artifact_id)}
    except Exception as exc:
        raise HTTPException(503, {"error_type": type(exc).__name__, "status": "artifact_unavailable"}) from None


class JobRequest(StrictModel):
    action: Literal["discover", "sleep", "transfer", "evaluate", "local_learn", "local_transfer", "local_audit"]
    seed: int = Field(default=11, ge=0, le=2147483647)
    episode_id: str = Field(default="", max_length=100)
    artifact_id: str = Field(default="", max_length=100)
    condition: Literal["none", "raw", "sleep", "flat", "local_rule"] = "sleep"
    max_actions: int = Field(default=40, ge=3, le=400)
    max_seconds: int = Field(default=600, ge=30, le=600)
    seeds: list[int] = Field(default=[101, 102, 103], min_length=1, max_length=5)
    conditions: list[Literal["none", "raw", "sleep", "flat"]] = Field(default=["none", "raw", "sleep"], min_length=1, max_length=4)


@app.post("/api/jobs")
def start_job(payload: JobRequest):
    if payload.action == "sleep" and not payload.episode_id:
        raise HTTPException(422, "Select a discovery episode first")
    if (payload.action == "evaluate" or (payload.action == "transfer" and payload.condition != "local_rule")) and not payload.artifact_id:
        raise HTTPException(422, "Select a completed sleep artifact first")
    if payload.action == 'transfer' and payload.condition == 'local_rule':
        try:
            rule=Memory(Settings.load()).get_local_rule()
        except Exception:
            raise HTTPException(503, 'Cannot read local learning from FalkorDB') from None
        if not rule:
            raise HTTPException(422, 'Run local learning first; no sleep artifact is needed')
        if payload.seed in rule.get('training_seeds', []):
            raise HTTPException(422, 'This seed contributed to local learning. Choose a fresh seed for transfer.')
    if payload.action == "sleep":
        try:
            episode = Memory(Settings.load()).get_episode(payload.episode_id)
        except ValueError:
            raise HTTPException(422, "Discovery episode not found. Select an episode from the list.") from None
        except Exception:
            raise HTTPException(503, "Cannot read the discovery episode from FalkorDB") from None
        if episode['kind'] != 'discovery' or episode['status'] == 'running':
            raise HTTPException(422, "Choose a completed discovery episode, not a transfer episode")
    try:
        return jobs.start(payload.action, payload.model_dump(exclude={"action"}))
    except ValueError:
        raise HTTPException(422, "Set the model API key and database host in Connections before running") from None
    except RuntimeError:
        raise HTTPException(409, "A run is already active") from None


@app.get("/api/jobs")
def list_jobs():
    return {"jobs": jobs.list()}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    try:
        return jobs.get(job_id)
    except KeyError:
        raise HTTPException(404, "Job not found") from None


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    try:
        return jobs.cancel(job_id)
    except KeyError:
        raise HTTPException(404, "Job not found") from None


@app.get("/api/replays")
def list_replays():
    # New records come from FalkorDB; legacy file exports remain readable.
    try:
        records = {j['id']:j for j in Memory(Settings.load()).list_jobs()}
    except Exception:
        records = {}
    for path in (ROOT / 'outputs' / 'runs').glob('job_*.json'):
        if path.stem not in records:
            try: records[path.stem] = json.loads(path.read_text(encoding='utf-8'))
            except (ValueError, OSError): continue
    items = [{k:j.get(k) for k in ('id','action','created_at','started_at','finished_at','status')} for j in records.values()]
    items.sort(key=lambda j:j.get('created_at') or '', reverse=True)
    return {'replays':[j['id'] for j in items], 'items':items}


@app.get("/api/replays/{replay_id}")
def get_replay(replay_id: str):
    if not re.fullmatch(r"job_[a-f0-9]{32}", replay_id):
        raise HTTPException(404, "Replay not found")
    try:
        return Memory(Settings.load()).get_job(replay_id)
    except Exception:
        pass
    path = ROOT / "outputs" / "runs" / f"{replay_id}.json"
    if not path.is_file():
        raise HTTPException(404, "Replay not found")
    return json.loads(path.read_text(encoding="utf-8"))



@app.get('/workshop')
def retired_workshop():
    return RedirectResponse('/incidents',status_code=307)


@app.get('/incidents')
def incident_page():
    return FileResponse(ROOT / 'static' / 'incidents.html')


class IncidentCreate(StrictModel):
    seed: int = Field(default=31, ge=0, le=2147483647)
    variant: Literal['combined','auth','queue'] = 'combined'


class IncidentStart(StrictModel):
    extra_requests: int = Field(default=0, ge=0, le=3)
    lab_id: str = Field(min_length=1, max_length=100, pattern=r'^incidentlab_[a-f0-9]{32}$')
    mode: Literal['train','compare','pilot','resume'] = 'pilot'


def incident_store():
    from .incident import IncidentStore
    return IncidentStore(Memory(Settings.load()))


@app.get('/api/incidents')
def incident_list():
    try:
        return {'labs':incident_store().list()}
    except Exception:
        raise HTTPException(503, 'Cannot read incident labs from FalkorDB') from None


@app.get('/api/incidents/{lab_id}')
def incident_get(lab_id: str):
    try:
        return incident_store().get(lab_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from None
    except Exception:
        raise HTTPException(503, 'Cannot read incident lab from FalkorDB') from None


@app.post('/api/incidents')
def incident_create(payload: IncidentCreate):
    try:
        return incident_store().create(payload.seed,payload.variant)
    except Exception:
        raise HTTPException(503, 'Cannot create incident lab in FalkorDB') from None


@app.post('/api/incident-jobs')
def incident_start(payload: IncidentStart):
    try:
        lab=incident_store().get(payload.lab_id)
        if jobs.busy():
            raise RuntimeError('Another run is active')
        if payload.extra_requests and payload.mode!='resume':
            raise ValueError('Extra requests are only available for explicit resume')
        if lab['calls_reserved'] >= lab['call_cap'] + payload.extra_requests:
            raise ValueError('This lab has reached its request cap; inspect its results.')
        if payload.mode!='resume' and any(r['status']!='complete' for r in lab['runs']):
            raise ValueError('This lab has an incomplete attempt. Inspect its saved error before starting another lab.')
        if payload.mode=='compare' and not {'source_a','source_b'}.issubset({r['kind'] for r in lab['runs']}):
            raise ValueError('Run the two specialist investigations first.')
        create_model(Settings.load())
        if payload.extra_requests:
            incident_store().extend_budget(payload.lab_id,payload.extra_requests)
        return jobs.start('incident',payload.model_dump())
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from None
    except RuntimeError:
        raise HTTPException(409,'Another run is active') from None
    except Exception:
        raise HTTPException(503,'Cannot start incident job; check FalkorDB and model configuration') from None


@app.get('/maze')
def maze_page():
    return FileResponse(ROOT / 'static' / 'maze.html')

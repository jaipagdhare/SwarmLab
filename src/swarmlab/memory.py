from datetime import datetime, timezone
import hashlib
import json
from threading import RLock
import uuid

from .config import Settings


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


class Memory:
    """One application writer; FalkorDB is required, never silently emulated."""

    def __init__(self, settings: Settings):
        if not settings.host:
            raise ValueError("Set FALKORDB_HOST in the local .env file")
        if settings.host not in {"localhost", "127.0.0.1", "::1"} and not settings.password:
            raise ValueError("Remote database connections require FALKORDB_PASSWORD")
        from falkordb import FalkorDB
        args = dict(host=settings.host, port=settings.port, username=settings.username or None,
                    password=settings.password or None, socket_connect_timeout=5, socket_timeout=15,
                    ssl=settings.tls)
        if settings.tls:
            args.update(ssl_cert_reqs="required", ssl_check_hostname=True)
        self.db = FalkorDB(**args)
        self.graph = self.db.select_graph(settings.graph)
        self.lock = RLock()

    def save_job(self, job):
        self.graph.query("MERGE (j:JobRun {id:$id}) SET j.action=$action, j.status=$status, j.created_at=$created, j.started_at=$started, j.finished_at=$finished, j.payload=$payload",
                         {"id":job['id'], "action":job['action'], "status":job['status'], "created":job['created_at'],
                          "started":job.get('started_at',''), "finished":job.get('finished_at',''), "payload":canonical(job)})

    def list_jobs(self):
        rows=self.graph.ro_query("MATCH (j:JobRun) RETURN j.payload ORDER BY j.created_at DESC LIMIT 100").result_set
        return [json.loads(r[0]) for r in rows]

    def get_job(self, job_id):
        rows=self.graph.ro_query("MATCH (j:JobRun {id:$id}) RETURN j.payload", {'id':job_id}).result_set
        if not rows: raise KeyError(job_id)
        return json.loads(rows[0][0])

    def list_artifacts(self):
        rows=self.graph.ro_query("MATCH (s:SleepRun {status:'complete'})-[:CONSOLIDATES]->(e:Episode) RETURN s.id,s.created_at,e.id,s.metadata ORDER BY s.created_at DESC LIMIT 100").result_set
        return [{'id':r[0],'created_at':r[1],'episode_id':r[2],'metadata':json.loads(r[3])} for r in rows]

    def register_policy(self, version, prompt):
        policy_id = version + '_' + digest(prompt)[:12]
        self.graph.query("MERGE (p:ControllerPolicy {id:$id}) SET p.version=$version, p.prompt=$prompt, p.prompt_digest=$digest",
                         {"id": policy_id, "version": version, "prompt": prompt, "digest": digest(prompt)})
        return policy_id

    def link_policy(self, episode_id, policy_id):
        self.graph.query("MATCH (e:Episode {id:$episode}), (p:ControllerPolicy {id:$policy}) MERGE (e)-[:USES_POLICY]->(p)",
                         {"episode": episode_id, "policy": policy_id})

    def probe(self):
        """Isolated node, never deletes or rewrites existing user data."""
        probe_id = new_id("probe")
        self.graph.query("CREATE (:ConnectionProbe {id:$id})", {"id": probe_id})
        found = self.graph.ro_query("MATCH (n:ConnectionProbe {id:$id}) RETURN n.id", {"id": probe_id}).result_set
        self.graph.query("MATCH (n:ConnectionProbe {id:$id}) DELETE n", {"id": probe_id})
        return found == [[probe_id]]

    def create_episode(self, seed: int, kind: str, condition="none", artifact_id=""):
        episode_id = new_id("episode")
        self.graph.query(
            "CREATE (e:Episode {id:$id, seed:$seed, kind:$kind, condition:$condition, artifact_id:$artifact, "
            "status:'running', created_at:$created, schema_version:1})",
            {"id": episode_id, "seed": seed, "kind": kind, "condition": condition,
             "artifact": artifact_id, "created": datetime.now(timezone.utc).isoformat()})
        return episode_id

    def append_experience(self, episode_id, event):
        event.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
        observation_id = new_id("obs")
        self.graph.query(
            "MATCH (e:Episode {id:$episode}) "
            "CREATE (o:Observation {id:$id, tick:$tick, payload:$payload}) "
            "CREATE (a:Action {id:$action_id, operation:$operation, robot_id:$robot}) "
            "CREATE (e)-[:CONTAINS]->(o) CREATE (e)-[:CONTAINS]->(a) CREATE (a)-[:PRODUCED]->(o)",
            {"episode": episode_id, "id": observation_id, "tick": event["tick"],
             "payload": canonical(event), "action_id": new_id("action"),
             "operation": event["action"]["operation"], "robot": event["action"]["robot_id"]})
        return observation_id

    def finish_episode(self, episode_id, result):
        self.graph.query("MATCH (e:Episode {id:$id}) SET e.status=$status, e.result=$result",
                         {"id": episode_id, "status": result["termination"], "result": canonical(result)})

    def get_episode(self, episode_id):
        rows = self.graph.ro_query(
            "MATCH (e:Episode {id:$id}) RETURN e.kind, e.status, e.result", {"id": episode_id}).result_set
        if not rows:
            raise ValueError("Episode not found")
        observations = self.graph.ro_query(
            "MATCH (:Episode {id:$id})-[:CONTAINS]->(o:Observation) RETURN o.id, o.payload ORDER BY o.tick",
            {"id": episode_id}).result_set
        return {"id": episode_id, "kind": rows[0][0], "status": rows[0][1],
                "result": json.loads(rows[0][2]) if rows[0][2] else None,
                "observations": [{"id": r[0], **json.loads(r[1])} for r in observations]}

    def list_episodes(self):
        rows = self.graph.ro_query(
            "MATCH (e:Episode) RETURN e.id, e.kind, e.condition, e.status, e.created_at ORDER BY e.created_at DESC LIMIT 100").result_set
        return [dict(zip(("id", "kind", "condition", "status", "created_at"), row)) for row in rows]

    def publish_sleep_artifact(self, episode_id, artifact, metadata):
        from .schemas import SleepArtifact
        parsed = SleepArtifact.model_validate(artifact)
        episode = self.get_episode(episode_id)
        if episode["kind"] != "discovery" or episode["status"] == "running":
            raise ValueError("Sleep requires a completed discovery episode")
        parsed.validate_evidence(episode["observations"])
        if metadata.get("validation_version") == "observed-facts-v1":
            from .schemas import validate_observed_facts
            validate_observed_facts(parsed, episode["observations"])
        artifact_id = new_id("sleep")
        snapshot_digest = digest(episode["observations"])
        with self.lock:
            self.graph.query(
                "MATCH (e:Episode {id:$episode}) "
                "CREATE (s:SleepRun {id:$id, status:'building', payload:$payload, metadata:$metadata, "
                "input_digest:$input_digest, artifact_digest:$artifact_digest, created_at:$created}) "
                "CREATE (s)-[:CONSOLIDATES]->(e)",
                {"episode": episode_id, "id": artifact_id, "payload": canonical(parsed.model_dump()),
                 "metadata": canonical(metadata), "input_digest": snapshot_digest,
                 "artifact_digest": digest(parsed.model_dump()), "created": datetime.now(timezone.utc).isoformat()})
            if metadata.get("policy_id"):
                self.graph.query("MATCH (s:SleepRun {id:$sleep}), (p:ControllerPolicy {id:$policy}) MERGE (s)-[:USES_POLICY]->(p)",
                                 {"sleep": artifact_id, "policy": metadata["policy_id"]})
            hypothesis_ids = {}
            for h in parsed.hypotheses:
                hypothesis_id = new_id("hypothesis")
                hypothesis_ids[h.local_id] = hypothesis_id
                self.graph.query(
                    "MATCH (s:SleepRun {id:$sleep}) "
                    "CREATE (h:Hypothesis {id:$id, description:$description, status:'candidate', payload:$payload}) "
                    "CREATE (s)-[:GENERATED]->(h)",
                    {"sleep": artifact_id, "id": hypothesis_id, "description": h.description, "payload": canonical(h.model_dump())})
                for observation_id in h.evidence_ids:
                    self.graph.query(
                        "MATCH (h:Hypothesis {id:$h}), (o:Observation {id:$o}) CREATE (h)-[:SUPPORTED_BY]->(o)",
                        {"h": hypothesis_id, "o": observation_id})
            for p in parsed.procedures:
                procedure_id = new_id("procedure")
                self.graph.query(
                    "MATCH (s:SleepRun {id:$sleep}) CREATE (p:ProcedureVersion {id:$id, title:$title, "
                    "status:'candidate', version:1, payload:$payload}) CREATE (s)-[:GENERATED]->(p)",
                    {"sleep": artifact_id, "id": procedure_id, "title": p.title, "payload": canonical(p.model_dump())})
                for local_id in p.hypothesis_ids:
                    self.graph.query(
                        "MATCH (p:ProcedureVersion {id:$p}), (h:Hypothesis {id:$h}) CREATE (p)-[:BASED_ON]->(h)",
                        {"p": procedure_id, "h": hypothesis_ids[local_id]})
            self.graph.query("MATCH (s:SleepRun {id:$id}) SET s.status='complete'", {"id": artifact_id})
        return self.get_artifact(artifact_id)

    def get_artifact(self, artifact_id):
        rows = self.graph.ro_query(
            "MATCH (s:SleepRun {id:$id, status:'complete'})-[:CONSOLIDATES]->(e:Episode) "
            "RETURN s.payload, s.metadata, s.input_digest, s.artifact_digest, e.id", {"id": artifact_id}).result_set
        if not rows:
            raise ValueError("Completed sleep artifact not found")
        row = rows[0]
        return {"id": artifact_id, "artifact": json.loads(row[0]), "metadata": json.loads(row[1]),
                "input_digest": row[2], "artifact_digest": row[3], "episode_id": row[4]}

    def retrieve_procedures_with_evidence(self, artifact_id):
        # Require completed publication even when no procedures were generated.
        artifact = self.get_artifact(artifact_id)
        rows = self.graph.ro_query(
            "MATCH (s:SleepRun {id:$id, status:'complete'})-[:GENERATED]->(p:ProcedureVersion)"
            "-[:BASED_ON]->(h:Hypothesis)-[:SUPPORTED_BY]->(o:Observation) "
            "RETURN p.id, p.payload, h.id, h.payload, o.id, o.payload ORDER BY p.id, h.id, o.id",
            {"id": artifact_id}).result_set
        paths = [{"procedure_id": row[0], "procedure": json.loads(row[1]),
                  "hypothesis_id": row[2], "hypothesis": json.loads(row[3]),
                  "observation_id": row[4], "observation": json.loads(row[5])} for row in rows]
        return {"artifact_id": artifact_id, "artifact_digest": artifact["artifact_digest"],
                "summary": artifact["artifact"]["summary"], "evidence_paths": paths}

    def record_context(self, episode_id, context):
        self.graph.query("MATCH (e:Episode {id:$id}) SET e.supplied_context=$context",
                         {"id": episode_id, "context": canonical(context)})

    def link_artifact_use(self, episode_id, artifact_id):
        self.graph.query(
            "MATCH (e:Episode {id:$episode}), (s:SleepRun {id:$artifact, status:'complete'}) "
            "MERGE (e)-[:USED]->(s)", {"episode": episode_id, "artifact": artifact_id})



    def ingest_local_episode(self, episode_id):
        from .local_learning import extract_samples
        episode=self.get_episode(episode_id)
        samples,events=extract_samples(episode['observations'])
        for sample in samples:
            self.graph.query('MATCH (o:Observation {id:$obs}) MERGE (s:LocalSample {id:$id}) SET s.bits=$bits,s.gate_open=$open,s.payload=$payload MERGE (s)-[:OBSERVED_IN]->(o)',
                             {'obs':sample['observation_id'],'id':sample['id'],'bits':sample['bits'],'open':sample['open'],'payload':canonical(sample)})
        for event in events:
            self.graph.query('MATCH (o:Observation {id:$obs}) MERGE (e:LearningEvent {id:$id}) SET e.payload=$payload MERGE (e)-[:TRIGGERED_BY]->(o)',
                             {'obs':event['observation_id'],'id':'event_'+digest(event)[:24],'payload':canonical(event)})
        return {'samples':len(samples),'events':len(events)}

    def refresh_local_rule(self):
        from .local_learning import induce
        samples=[json.loads(r[0]) for r in self.graph.ro_query('MATCH (s:LocalSample) RETURN s.payload ORDER BY s.id').result_set]
        rule=induce(samples)
        rule["training_seeds"] = sorted(r[0] for r in self.graph.ro_query("MATCH (:LocalSample)-[:OBSERVED_IN]->(o:Observation)<-[:CONTAINS]-(e:Episode) RETURN DISTINCT e.seed").result_set)
        rule_id='localrule_'+digest(rule)[:24]
        self.graph.query('MERGE (r:LocalRule {id:$id}) SET r.payload=$payload,r.status=$status,r.updated_at=$now',
                         {'id':rule_id,'payload':canonical(rule),'status':rule['status'],'now':datetime.now(timezone.utc).isoformat()})
        self.graph.query('MATCH (r:LocalRule {id:$id}),(s:LocalSample) MERGE (r)-[:SUPPORTED_BY]->(s)',{'id':rule_id})
        self.graph.query("MERGE (h:LocalLearningHead {id:'current'}) WITH h OPTIONAL MATCH (h)-[old:CURRENT]->() DELETE old WITH h MATCH (r:LocalRule {id:$id}) MERGE (h)-[:CURRENT]->(r)",{'id':rule_id})
        return {'id':rule_id,**rule}

    def get_local_rule(self, rule_id=None):
        if rule_id:
            rows=self.graph.ro_query('MATCH (r:LocalRule {id:$id}) RETURN r.id,r.payload',{'id':rule_id}).result_set
        else:
            rows=self.graph.ro_query("MATCH (:LocalLearningHead {id:'current'})-[:CURRENT]->(r:LocalRule) RETURN r.id,r.payload").result_set
        if not rows: return None
        return {'id':rows[0][0],**json.loads(rows[0][1])}

    def retrieve_local_memory(self, rule_id=None):
        """Freeze a rule and fetch representative evidence through its graph edges."""
        rule=self.get_local_rule(rule_id)
        if rule is None:
            raise ValueError('No local learning exists yet. Run Review past events or Learn with local experiments.')
        rows=self.graph.ro_query('MATCH (r:LocalRule {id:$id})-[:SUPPORTED_BY]->(s:LocalSample)-[:OBSERVED_IN]->(o:Observation) RETURN s.payload,o.payload ORDER BY s.id',{'id':rule['id']}).result_set
        evidence=[];seen=set()
        for sample_payload, observation_payload in rows:
            sample=json.loads(sample_payload);key=(sample['bits'],sample['open'])
            if key in seen: continue
            seen.add(key);observation=json.loads(observation_payload)
            view=observation[sample['phase']]
            evidence.append({'sample_id':sample['id'],'observation_id':sample['observation_id'],
                             'phase':sample['phase'],'occupancy_bits':sample['bits'],'gate_open':sample['open'],
                             'observed_view':{k:view[k] for k in ('tick','robot_id','position','objects','robots')}})
        return {'rule':rule,'evidence':evidence}

    def link_local_rule_use(self, episode_id, rule_id):
        self.graph.query('MATCH (e:Episode {id:$episode}),(r:LocalRule {id:$rule}) MERGE (e)-[:USED_LOCAL_RULE]->(r)',
                         {'episode':episode_id,'rule':rule_id})

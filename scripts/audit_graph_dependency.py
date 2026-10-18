"""Prove core memory depends on FalkorDB and its edges. Zero model calls.

Uses a uniquely named scratch graph and removes only that graph. Never stops
or modifies the user's application graph. Run after configuring local .env.
"""
from dataclasses import replace
import json
import socket
import uuid

from swarmlab.config import Settings
from swarmlab.memory import Memory, canonical
from swarmlab.incident import IncidentStore, IncidentWorld
from swarmlab.local_runner import run_local


def main():
    settings=Settings.load()
    scratch=Memory(replace(settings,graph='audit_'+uuid.uuid4().hex))
    results={}
    try:
        store=IncidentStore(scratch)
        lab=store.create(31,'combined')
        event=IncidentWorld(31,'auth').step('inspect_auth')
        run={'id':'audit_source','kind':'source_a','status':'complete','created_at':'2026-10-18T00:00:00Z',
             'events':[event],'calls':[],'retrieved_ids':[]}
        store.save(lab['id'],run)
        assert len(store.evidence(lab['id']))==1
        # Keep every node and payload, remove only the producer-to-evidence edge.
        scratch.graph.query('MATCH (:IncidentRun {id:$id})-[e:OBSERVED]->(:IncidentObservation) DELETE e',{'id':run['id']})
        assert store.evidence(lab['id'])==[]
        count=scratch.graph.ro_query('MATCH (o:IncidentObservation) RETURN count(o)').result_set[0][0]
        assert count==1
        results['incident_retrieval_requires_provenance_edge']=True
        # Keep the local rule payload, disconnect its authoritative head.
        rule={'id':'audit_rule','table':{'00':False,'01':False,'10':False,'11':True},'status':'validated_in_scope'}
        scratch.graph.query('CREATE (h:LocalLearningHead {id:"current"}) CREATE (r:LocalRule {id:$id,payload:$p}) CREATE (h)-[:CURRENT]->(r)',{'id':rule['id'],'p':canonical(rule)})
        assert scratch.get_local_rule()['id']=='audit_rule'
        scratch.graph.query('MATCH (:LocalLearningHead)-[e:CURRENT]->(:LocalRule) DELETE e')
        assert scratch.get_local_rule() is None
        results['local_memory_requires_current_rule_edge']=True
    finally:
        scratch.graph.delete()
    # Bound-but-not-listening loopback socket: isolated unavailable endpoint.
    with socket.socket() as closed_service:
        closed_service.bind(('127.0.0.1',0))
        dead_settings=replace(settings,host='127.0.0.1',port=closed_service.getsockname()[1],username='',password='',tls=False)
        for name,action in [
            ('incident_fails_without_db',lambda:IncidentStore(Memory(dead_settings)).get('missing')),
            ('maze_transfer_fails_without_db',lambda:run_local(Memory(dead_settings),mode='transfer',seed=701))]:
            try:action()
            except Exception as exc:
                if type(exc).__name__ not in ('ConnectionError','TimeoutError'):
                    raise
                results[name]=True
            else:raise AssertionError(name+' unexpectedly succeeded')
    print(json.dumps({'checks':results,'model_calls':0,'production_graph_modified':False},indent=2))


if __name__=='__main__':main()

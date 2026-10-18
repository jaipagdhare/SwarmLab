from copy import deepcopy
import pytest
from swarmlab.incident import IncidentWorld, memory_context, run_incident
from swarmlab.model import Completion, ModelError


def test_repair_order_and_data_loss():
    w=IncidentWorld(31,'combined')
    assert w.step('resume_queue')['outcome']['dispatch']=='paused_again'
    w.step('reload_worker')
    assert not w.verify()['success']
    w.step('resume_queue')
    assert w.verify()['success']
    w.step('reset_database')
    assert w.verify()['jobs_lost']>0
    assert not w.verify()['success']


def test_single_faults_and_identical_initial_observations():
    for variant, action in [('auth','reload_worker'),('queue','resume_queue')]:
        w=IncidentWorld(31,variant)
        assert not w.verify()['success']
        w.step(action)
        assert w.verify()['success']
    assert IncidentWorld(31,'auth').view()==IncidentWorld(31,'combined').view()
    assert IncidentWorld(31,'queue').view()==IncidentWorld(31,'combined').view()


class Store:
    def __init__(self):
        self.lab={'id':'test','seed':31,'variant':'combined','call_cap':10,'runs':[]}
    def get(self,lab):
        d=deepcopy(self.lab);d['calls_reserved']=sum(len(r['calls']) for r in d['runs']);return d
    def save(self,lab,run):
        self.lab['runs']=[r for r in self.lab['runs'] if r['id']!=run['id']]+[deepcopy(run)]
    def evidence(self,lab):
        return [{'producer':r['kind'],**e} for r in self.lab['runs'] if r['kind'].startswith('source_') and r['status']=='complete' for e in r['events']]


class Model:
    name='test-double'
    max_attempts=3
    def __init__(self):self.contexts=[]
    def complete(self,**kw):
        c=kw['context'];self.contexts.append(deepcopy(c))
        assert 'seed' not in c and 'variant' not in c
        actions=['inspect_auth','inspect_queue'] if c['phase']=='diagnose' else ['reload_worker','resume_queue']
        return Completion({'rationale':'test only','actions':actions,'evidence_ids':[]},{'tokens':1},0.01)


def test_complete_pilot_isolated_contexts_same_evidence_and_cap():
    store,model=Store(),Model()
    result=run_incident(store,model,'test')
    assert result['calls_reserved']==10
    assert model.max_attempts==1
    assert len(result['runs'])==5
    assert all(r['score']['success'] for r in result['runs']) # Baseline can succeed.
    assert all(not c['historical_memory'] for c in model.contexts[:6])
    trials={r['kind']:r for r in result['runs']}
    assert trials['none']['initial_view']==trials['raw']['initial_view']==trials['graph']['initial_view']
    assert trials['raw']['retrieved_ids']==trials['graph']['retrieved_ids']
    assert len(trials['raw']['retrieved_ids'])==8
    raw=model.contexts[6]['historical_memory']['chronological_observations']
    graph=[e for group in model.contexts[8]['historical_memory']['component_evidence'].values() for e in group]
    assert sorted(raw,key=lambda e:e['id'])==sorted(graph,key=lambda e:e['id'])
    assert all(e['producer'].startswith('source_') for e in graph)
    run_incident(store,model,'test')
    assert len(model.contexts)==10 # Completed stages are idempotent.


def test_failed_call_is_reserved_and_no_retry():
    class Failure(Model):
        def complete(self,**kw):raise ModelError('quota')
    store=Store()
    with pytest.raises(ModelError):run_incident(store,Failure(),'test')
    assert store.get('test')['calls_reserved']==1
    assert store.lab['runs'][0]['status']=='incomplete'
    with pytest.raises(ValueError,match='incomplete'):run_incident(store,Model(),'test')


def test_bad_citation_rejected_and_usage_saved():
    class BadCitation(Model):
        def complete(self,**kw):return Completion({'rationale':'test','actions':['inspect_auth'],'evidence_ids':['invented']},{'tokens':12},0.01)
    store=Store()
    with pytest.raises(ValueError,match='cited evidence'):run_incident(store,BadCitation(),'test')
    assert store.lab['runs'][0]['calls'][0]['usage']=={'tokens':12}
    assert not store.lab['runs'][0]['events']


def test_cancelled_run_spends_no_calls():
    store,model=Store(),Model()
    run_incident(store,model,'test',cancelled=lambda:True)
    assert not model.contexts


def test_no_memory_cannot_receive_history():
    assert memory_context('none',[{'secret':'source data'}])=={}


def test_current_observation_citations_are_valid_for_fresh_agents():
    class Citing(Model):
        def complete(self,**kw):
            reply=super().complete(**kw)
            if kw['context']['current_history']:
                oid=kw['context']['current_history'][0]['id']
                assert oid in kw['schema']['properties']['evidence_ids']['items']['enum']
                reply.value['evidence_ids']=[oid]
            return reply
    store=Store()
    result=run_incident(store,Citing(),'test')
    assert all(r['status']=='complete' for r in result['runs'])
    assert result['runs'][0]['calls'][1]['raw_response']['evidence_ids']


def test_quota_resume_only_requests_missing_phase_and_keeps_prior_results():
    class QuotaAtEnd(Model):
        def complete(self,**kw):
            if len(self.contexts)==9:
                raise ModelError('gemini_daily_or_unavailable_quota')
            return super().complete(**kw)
    store=Store()
    with pytest.raises(ModelError):run_incident(store,QuotaAtEnd(),'test')
    before=deepcopy(store.lab['runs'])
    assert len(before)==5 and before[-1]['status']=='incomplete'
    assert len(before[-1]['events'])==2
    store.lab['call_cap']=11 # Explicit user-approved extension.
    resumed=Model()
    result=run_incident(store,resumed,'test',mode='resume')
    assert len(resumed.contexts)==1
    assert resumed.contexts[0]['phase']=='repair'
    assert result['runs'][:4]==before[:4]
    assert result['runs'][-1]['events'][:2]==before[-1]['events']
    assert result['runs'][-1]['score']['success']
    assert result['calls_reserved']==11


def test_v3_measures_before_after_and_allows_recovery_for_every_consumer():
    class NeedsRecovery(Model):
        def complete(self,**kw):
            result=super().complete(**kw)
            c=kw['context']
            # All consumers initially try only the queue; source A has baseline records.
            if c['phase']=='repair' and not any(e.get('protocol_measurement') for e in c['current_history']):
                result.value['actions']=['resume_queue']
            if c['phase']=='recover':
                result.value['actions']=['reload_worker','resume_queue']
            return result
    store=Store();store.lab.update(protocol_version=3,call_cap=13)
    result=run_incident(store,NeedsRecovery(),'test')
    assert result['calls_reserved']==13
    for run in result['runs'][:2]:
        assert [e['action'] for e in run['events'] if e.get('protocol_measurement')=='baseline']==['inspect_auth','inspect_queue']
        assert [e['action'] for e in run['events'] if e.get('protocol_measurement')=='after_intervention']==['inspect_auth','inspect_queue']
    for run in result['runs'][2:]:
        assert run['score']['success']
        assert run['calls'][-1]['context']['phase']=='recover'
        assert run['calls'][-1]['context']['current_history'][-1]['outcome']['authentication']=='rejected'


def test_resume_received_completion_uses_no_new_request():
    store=Store();run_incident(store,Model(),'test',mode='train')
    run=store.lab['runs'][-1]
    # Simulate crash after response persistence but before simulator execution.
    run['status']='incomplete';run.pop('score');run['completed_phases']=['diagnose']
    run['events']=run['events'][:2]
    run['calls'][-1]['status']='received'
    class NoRequest(Model):
        def complete(self,**kw):raise AssertionError('Previously received response must be reused')
    # Only train stages requested by trimming fixture to B completion plus quota-free stage restore.
    # Resume also schedules consumers; stop immediately after B is restored.
    def cancelled(): return store.lab['runs'][-1]['status']=='complete'
    run_incident(store,NoRequest(),'test',mode='resume',cancelled=cancelled)
    assert store.lab['runs'][1]['status']=='complete'
    assert len(store.lab['runs'][1]['events'])==4

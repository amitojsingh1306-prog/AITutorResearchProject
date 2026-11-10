import json
from pathlib import Path
from scripts.run_panel_evaluation import select_pairs, summarize, paired_intervals
from backend.memory.graph_memory import Neo4jMemory,retrieval_terms
from types import SimpleNamespace


def test_official_subset_selection_is_fixed_and_category_balanced():
    root=Path(__file__).resolve().parents[2]
    samples=json.loads((root/'benchmark_data/locomo/locomo10.json').read_text())
    selected=select_pairs(samples,10,1)
    assert len(selected)==49 and len({s['sample_id'] for s,_,_ in selected})==10
    assert len({(s['sample_id'],q['category']) for s,_,q in selected})==49
    assert select_pairs(samples,1,1)==[x for x in selected if x[0]['sample_id']==samples[0]['sample_id']]


def test_aggregation_does_not_mix_abstention_with_f1_or_hide_errors():
    rows=[{'mode':'buffer','sample_id':'c','qa_index':0,'repeat':0,'category':4,'official_score':.5},
          {'mode':'buffer','sample_id':'c','qa_index':1,'repeat':0,'category':5,'official_score':1.},
          {'mode':'buffer','sample_id':'c','qa_index':2,'repeat':0,'category':2,'error':'unavailable'}]
    result=summarize(rows)['buffer']
    assert result['mean_answer_f1_categories_1_4']==.5
    assert result['abstention_phrase_score_category_5']==1
    assert result['attempted']==3 and result['completed']==2 and result['errors']==1


def test_pairing_keeps_trial_and_conversation_identity():
    rows=[]
    for conversation in ['a','b']:
        for repeat in [0,1]:
            for mode,score in [('buffer',.1),('vector',.4)]:
                rows.append({'mode':mode,'sample_id':conversation,'qa_index':0,'repeat':repeat,'category':4,'official_score':score})
    result=paired_intervals(rows)['vector']
    assert result['conversations']==2 and result['paired_predictions']==4
    assert abs(result['paired_f1_difference']-.3)<1e-10


def test_graph_fallback_is_scoped_and_is_not_claimed_as_structured_fact():
    graph=object.__new__(Neo4jMemory);graph.scope='fixture';graph.sync=lambda user:None
    calls=[]
    def run(query,**parameters):
        calls.append((query,parameters))
        if len(calls)==1:return []
        return [{'kind':'source_excerpt','value':'An event','topic':None,'source_message_id':'old',
            'source_text':'The charity event supports literacy.','timestamp':'2026-11-07T00:00:00+00:00',
            'chat_id':'chat','used_topic_join':False,'lexical_overlap':2}]
    graph.run=run
    facts,trace=graph.retrieve(SimpleNamespace(content='What did the charity event support?',user_id='learner-A',id='current'))
    assert trace['retrieval_method']=='source_keyword_fallback'
    assert facts[0]['kind']=='source_excerpt' and not facts[0]['included_in_prompt']
    assert calls[1][1]['user_id']=='learner-A' and calls[1][1]['current']=='current'
    assert 'charity' in retrieval_terms('What did the charity event support?')

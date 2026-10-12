import pytest
from yopo_eval.aggregate import aggregate


def protocol():
    return {'tasks':[{'condition':'sparse'}], 'episodes':[{'id':str(i),'model':'test_model','task_index':0,'speed_mps':4,'paper_first10':True} for i in range(4)]}


def test_failures_remain_and_missing_never_become_success():
    records={'0':{'status':'success','metrics':{'path_length_m':50}},'1':{'status':'collision','metrics':{'path_length_m':2}}}
    result=aggregate(protocol(),records);row=result['groups'][0]
    assert result['status']=='incomplete' and result['missing_episodes']==2
    assert row['success_rate_among_completed']==.5 and row['possible_final_success_rate_bounds']==[.25,.75]
    assert row['all_attempts']['path_length_m']['mean']==26
    assert row['successful_only']['path_length_m']['mean']==50


def test_empty_matrix_is_unknown_not_zero_or_complete():
    result=aggregate(protocol(),{});row=result['groups'][0]
    assert result['status']=='incomplete'
    assert row['success_rate_among_completed'] is None and row['wilson95_among_completed'] is None


def test_nonterminal_state_cannot_complete_a_slot():
    with pytest.raises(ValueError):aggregate(protocol(),{'0':{'status':'running'}})

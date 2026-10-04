"""Opt-in real network end-to-end test: no fake model/provider fallback."""
import os
import pytest
from graph import graph
from tests.test_all_requirements import REQUEST

@pytest.mark.integration
def test_live_end_to_end():
    if os.getenv('RUN_LIVE_TESTS')!='1':
        pytest.skip('Set RUN_LIVE_TESTS=1 to explicitly enable live provider calls')
    result=graph.invoke({'user_requirements':REQUEST},{'recursion_limit':1000})['trip_plan']
    assert len(result['days'])==4
    assert result['tool_trace'], 'No live LLM tool calls succeeded; inspect credentials/model access'
    assert all(x['date']==result['days'][x['day']-1]['date'] for x in result['tool_trace'])

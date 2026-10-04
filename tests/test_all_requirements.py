"""Contract tests superseding the retired replanning/fallback-price requirements."""
import json
from datetime import datetime, timezone
from unittest.mock import Mock
import pytest
from langchain_core.messages import AIMessage, ToolMessage
import graph as workflow
from graph import create_graph
from schemas.travel import TravelRequest
from utils.budget import calculate_budget
from fastapi.testclient import TestClient
import api

REQUEST = {'source_city':'BLR','destination':'Goa','start_date':'2026-10-10','end_date':'2026-10-13','passengers':2,'budget':'30000 INR','random_seed':17}

class ScriptedModel:
    """Test double only: never used as a production LLM or provider."""
    def __init__(self):
        self.histories=[]
    def bind_tools(self, tools, **kwargs):
        assert {t.name for t in tools} == {'get_weather','search_transport','search_stay','search_wikipedia','random_choice'}
        return self
    def invoke(self,messages):
        if 'blueprint' in messages[0].content:
            return AIMessage(content=json.dumps({'days':[{'theme':'Explore'}]*4}))
        self.histories.append(messages)
        context=json.loads(messages[1].content)
        day=context['day']
        results=[m for m in messages if isinstance(m,ToolMessage)]
        if not results:
            calls=[('get_weather',{'location':context['location'],'date':context['date']}),('search_wikipedia',{'query':'famous places temples','category':'places'}),('search_wikipedia',{'query':'famous food','category':'food'})]
            calls += [('search_transport',{'leg_id':l['id']}) for l in context['transport_legs']]
            calls += [('search_stay',{'stay_id':s['id']}) for s in context['stay_periods']]
        elif not any(m.name=='random_choice' for m in results):
            items=json.loads(next(m.content for m in results if m.name=='search_wikipedia'))['places']
            calls=[('random_choice',{'candidate_ids':[x['candidate_id'] for x in items],'count':1})]
        else:
            selected=json.loads(next(m.content for m in results if m.name=='random_choice'))['selected']
            return AIMessage(content=json.dumps({'places':[x['candidate_id'] for x in selected], 'morning':[selected[0]['candidate_id']],'evening':['invented-id']}))
        return AIMessage(content='',tool_calls=[{'name':n,'args':a,'id':f'd{day}-{len(results)}-{i}'} for i,(n,a) in enumerate(calls)])

@pytest.fixture
def providers(monkeypatch):
    weather=Mock(side_effect=lambda location,date: {'success':True,'status':'SUCCESS','location':location,'date':date,'temperature':27,'source':'test fixture'})
    flights=Mock(return_value={'success':True,'source':'test fixture','currency':'INR','price':2500.25})
    stay=Mock(return_value={'success':True,'status':'SUCCESS','source':'test fixture','currency':'INR','name':'Provider fixture','total_price':6000.50})
    places=Mock(return_value={'status':'SUCCESS','places':[{'name':'Fort Aguada','description':'Fixture for verified page','url':'https://en.wikipedia.org/wiki/Fort_Aguada'},{'name':'Baga Beach','url':'https://en.wikipedia.org/wiki/Baga_Beach'}]})
    food=Mock(return_value={'status':'SUCCESS','food_items':[{'name':'Goan cuisine','url':'https://en.wikipedia.org/wiki/Goan_cuisine'}]})
    for name,mock in [('get_live_weather',weather),('search_ignav_flights',flights),('search_stay_hotels',stay),('search_wikipedia_places',places),('search_wikipedia_food',food)]:
        monkeypatch.setattr(workflow,name,mock)
    return weather,flights,stay

def run(model=None,req=None):
    model=model or ScriptedModel()
    return create_graph(lambda:model).invoke({'user_requirements':req or REQUEST},{'recursion_limit':1000})

def test_multiday_tool_flow_and_integrity(providers):
    model=ScriptedModel(); result=run(model); trip=result['trip_plan']
    assert len(trip['days'])==4
    assert [d['date'] for d in trip['days']]==['2026-10-10','2026-10-11','2026-10-12','2026-10-13']
    assert providers[0].call_count==4
    assert providers[1].call_count==2
    assert providers[2].call_count==1
    assert providers[1].call_args_list[0].kwargs['passengers']==2
    assert providers[2].call_args.args[1:4]==('2026-10-10','2026-10-13',2)
    assert any(any(isinstance(m,ToolMessage) for m in history) for history in model.histories)
    for history in model.histories:
        if len(history)>2:
            day=json.loads(history[1].content)['day']
            assert all(m.tool_call_id.startswith(f'd{day}-') for m in history if isinstance(m,ToolMessage))
    assert all(not d['evening'] for d in trip['days'])
    assert trip['budget']['total']==11001.0
    assert trip['budget']['status']=='PARTIAL'
    assert trip['budget']['within_budget'] is None
    assert trip['randomization']['decisions']==run()['trip_plan']['randomization']['decisions']
    assert all(set(d['selected'])<=set(d['candidates']) for d in trip['randomization']['decisions'])
    assert 'replan' not in create_graph().get_graph().nodes

def test_location_progression_and_periods(providers):
    result=run(req={**REQUEST,'day_locations':['Goa','Goa','Panaji','Panaji']})
    assert providers[0].call_args_list[2].kwargs=={'location':'Panaji','date':'2026-10-12'}
    assert len(result['stay_periods'])==2
    assert [s['nights'] for s in result['stay_periods']]==[2,1]
    assert providers[1].call_count==2
    assert providers[2].call_count==2

def test_provider_failure_no_fabrication(providers):
    providers[0].side_effect=RuntimeError('failure')
    providers[1].return_value=workflow.unavailable('Not configured')
    providers[2].return_value=workflow.unavailable('Not configured')
    trip=run()['trip_plan']
    assert len(trip['days'])==4
    assert trip['budget']['total']==0
    assert all(not d['weather'].get('temperature') for d in trip['days'])
    assert any('weather' in w.lower() for w in trip['warnings'])

def test_missing_model_is_honest(monkeypatch):
    def missing(): raise ValueError('Missing credentials')
    trip=create_graph(missing).invoke({'user_requirements':REQUEST},{'recursion_limit':1000})['trip_plan']
    assert len(trip['days'])==4
    assert all(not d['places'] and not d['morning'] for d in trip['days'])
    assert trip['budget']['total']==0
    assert trip['warnings']

@pytest.mark.parametrize('changes',[{'passengers':0},{'source_city':''},{'end_date':'2026-10-09'},{'budget':'-1'},{'budget':'nan'},{'day_locations':['Goa']}])
def test_request_validation(changes):
    with pytest.raises(ValueError): TravelRequest.model_validate({**REQUEST,**changes})

def test_api_canonical_response(providers,monkeypatch):
    monkeypatch.setattr(api,'graph',create_graph(lambda:ScriptedModel()))
    client=TestClient(api.app)
    response=client.post('/plan-trip',json=REQUEST)
    assert response.status_code==200
    assert {'metadata','days','budget','transport','accommodation','randomization','warnings','tool_trace'}<=response.json()['data'].keys()
    assert client.post('/api/plan',json={**REQUEST,'passengers':0}).status_code==422

def test_weather_local_timezone_and_invalid_date(monkeypatch):
    from services.weather_service import get_weather
    monkeypatch.setenv('OPENWEATHER_API_KEY','test')
    timestamp=int(datetime(2026,10,10,23,tzinfo=timezone.utc).timestamp())
    response=Mock(status_code=200)
    response.json.return_value={'city':{'timezone':19800},'list':[{'dt':timestamp,'main':{'temp':28},'weather':[{'main':'Clouds'}]}]}
    monkeypatch.setattr('services.weather_service.requests.get',Mock(return_value=response))
    assert get_weather('Goa','2026-10-11')['temperature']==28
    assert not get_weather('Goa','2026-10-10')['success']
    assert not get_weather('Goa','invalid')['success']
    assert get_weather('Goa','2026-10-11')['rain_probability'] is None

def test_ignav_occupancy_currency_and_no_defaults(monkeypatch):
    import services.ignav_service as provider
    monkeypatch.setenv('IGNAV_API_KEY','test')
    response=Mock(status_code=200)
    response.json.return_value={'itineraries':[{'price':{'amount':100,'currency':'USD','status':'verified'},'outbound':{'segments':[]}}]}
    post=Mock(return_value=response); monkeypatch.setattr(provider.requests,'post',post)
    result=provider.search_flights('BLR','GOI','2026-10-10',adults=2)
    assert post.call_args.kwargs['json']['adults']==2
    assert result['price']==100 and result['currency']=='USD'
    assert result['duration_minutes'] is None and result['airline'] is None
    response.json.return_value['itineraries'][0]['price']['status']='unverified'
    assert provider.search_flights('BLR','GOI','2026-10-10')['price'] is None

def test_staying_live_contract(monkeypatch):
    from services.hotel_service import search_stay_hotels
    monkeypatch.setenv('STAYING_API_KEY','test')
    response=Mock(status_code=200)
    response.json.return_value={'data':[{'name':'Returned property','price':{'currency':'INR','totalPrice':1234.56,'nightlyPrice':None}}]}
    get=Mock(return_value=response); monkeypatch.setattr('services.hotel_service.requests.get',get)
    result=search_stay_hotels('Goa','2026-10-10','2026-10-13',2)
    assert result['total_price']==1234.56
    assert get.call_args.kwargs['params']['checkOut']=='2026-10-13'
    assert result['price_per_night'] is None


def test_budget_determinism_no_exchange_fallback():
    state={'user_requirements':REQUEST,'transport_legs':[{'origin':'BLR','destination':'GOI','departure_date':'2026-10-10','result':{'success':True,'price':100,'currency':'USD'}}],'stay_periods':[],'daily_plans':[]}
    assert calculate_budget(state)==calculate_budget(state)
    assert calculate_budget(state)['total']==0
    assert calculate_budget(state)['entries'][0]['provenance']=='UNAVAILABLE'

def test_reject_wrong_weather_and_fake_random_candidates(providers):
    state=workflow.validate_request({'user_requirements':REQUEST})
    state.update(workflow.create_trip_blueprint(state,lambda:ScriptedModel()))
    state.update(workflow.initialize_day(state))
    state['messages'].append(AIMessage(content='',tool_calls=[{'id':'bad-date','name':'get_weather','args':{'location':'Goa','date':'2026-10-11'}},{'id':'fake','name':'random_choice','args':{'candidate_ids':['invented'],'count':1}}]))
    result=workflow.execute_tools_node(state)
    assert providers[0].call_count==0
    assert len(result['messages'])==5
    assert all(not json.loads(m.content)['success'] for m in result['messages'][-2:])
    assert not result['random_decisions']


def test_loop_ceiling_and_unknown_tool(providers):
    class Runaway(ScriptedModel):
        def invoke(self,messages):
            if 'blueprint' in messages[0].content:
                return AIMessage(content=json.dumps({'days':[{}]*4}))
            return AIMessage(content='',tool_calls=[{'id':str(len(messages)), 'name':'unknown','args':{}}])
    result=run(Runaway())
    assert len(result['daily_plans'])==4
    assert len(result['tool_trace'])==4*(workflow.MAX_TOOL_ROUNDS+1)
    assert all(not t['result']['success'] for t in result['tool_trace'])
    assert len([m for m in result['messages'] if isinstance(m,ToolMessage)])==workflow.MAX_TOOL_ROUNDS+1


def test_single_day_zero_nights_and_no_duplicate_costs(providers):
    trip=run(req={**REQUEST,'end_date':'2026-10-10'})['trip_plan']
    assert not trip['accommodation']
    assert providers[2].call_count==0
    assert trip['budget']['nights_counted']==0
    assert trip['budget']['total']==5000.50


def test_wikipedia_provider_no_prices(monkeypatch):
    from services.wikipedia_service import search_wikipedia_places, search_wikipedia_food
    search=Mock(status_code=200)
    search.json.return_value={'query':{'search':[{'title':'Fort Aguada','snippet':'Historical site'}]}}
    extracts=Mock(status_code=200)
    extracts.json.return_value={'query':{'pages':{'1':{'title':'Fort Aguada','extract':'Documented historical site','fullurl':'https://en.wikipedia.org/wiki/Fort_Aguada'}}}}
    monkeypatch.setattr('services.wikipedia_service.requests.get',Mock(side_effect=[search,extracts,search,extracts]))
    assert search_wikipedia_places('Goa')['places'][0]['estimated_cost'] is None
    assert search_wikipedia_food('Goa')['food_items'][0]['estimated_cost'] is None

def test_transient_model_throttle_retries_same_messages(monkeypatch):
    import httpx
    from groq import RateLimitError
    messages=[AIMessage(content='same request')]
    response=httpx.Response(429,request=httpx.Request('POST','https://api.groq.com/test'),headers={'retry-after':'1'})
    model=Mock()
    model.invoke.side_effect=[RateLimitError('throttled',response=response,body={}),AIMessage(content='{}')]
    sleep=Mock(); monkeypatch.setattr(workflow.time,'sleep',sleep)
    assert workflow.invoke_model(model,messages).content=='{}'
    assert model.invoke.call_args_list[0]==model.invoke.call_args_list[1]
    assert sleep.call_count==1

def test_streamlit_generated_trip_renders(providers,monkeypatch):
    from streamlit.testing.v1 import AppTest
    response=Mock(status_code=200)
    response.json.return_value={'status':'success','data':run()['trip_plan']}
    monkeypatch.setattr('requests.post',Mock(return_value=response))
    app_test=AppTest.from_file('app.py').run(timeout=20)
    app_test.text_input[0].set_value('Bangalore')
    app_test.text_input[1].set_value('Goa')
    app_test.button[0].click().run(timeout=20)
    assert not app_test.exception
    assert any('Known subtotal' in metric.label for metric in app_test.metric)

def test_sandbox_accommodation_never_accepted_as_live(monkeypatch):
    from services.hotel_service import search_stay_hotels
    get=Mock(); monkeypatch.setattr('services.hotel_service.requests.get',get)
    monkeypatch.setenv('STAYING_API_KEY','stay_test_fixture')
    assert not search_stay_hotels('Goa','2026-10-10','2026-10-13')['success']
    get.assert_not_called()
    monkeypatch.setenv('STAYING_API_KEY','stay_live_fixture')
    response=Mock(status_code=200)
    response.json.return_value={'data':[{'name':'Sandbox property'}],'meta':{'warnings':[{'code':'sandbox_data'}]}}
    get.return_value=response
    result=search_stay_hotels('Goa','2026-10-10','2026-10-13')
    assert result['source_type']=='UNAVAILABLE'
    assert not result['hotels']

def test_ceiling_uses_json_synthesis_without_further_tools():
    state=workflow.validate_request({'user_requirements':REQUEST})
    state.update(workflow.create_trip_blueprint(state,lambda:ScriptedModel()))
    state.update(workflow.initialize_day(state))
    candidate={'candidate_id':'verified','name':'Returned page','kind':'places','url':'https://en.wikipedia.org/wiki/Goa'}
    state['candidate_registry']={'verified':candidate}
    state['tool_rounds']=workflow.MAX_TOOL_ROUNDS
    model=Mock()
    model.bind.return_value.invoke.return_value=AIMessage(content=json.dumps({'morning':['verified']}))
    state.update(workflow.planner_decides_tools(state,lambda:model))
    model.bind.assert_called_once_with(response_format={'type':'json_object'})
    model.bind_tools.assert_not_called()
    assert not state['messages'][-1].tool_calls
    assert workflow.build_daily_plan(state)['daily_plans'][0]['morning']==[candidate]

def test_daily_quota_stops_remaining_model_requests(monkeypatch):
    import httpx
    from groq import RateLimitError
    response=httpx.Response(429,request=httpx.Request('POST','https://api.groq.com/test'))
    error=RateLimitError('Daily quota',response=response,body={'error':{'message':'Rate limit reached on tokens per day (TPD)'}})
    model=Mock(); model.invoke.side_effect=error
    sleep=Mock(); monkeypatch.setattr(workflow.time,'sleep',sleep)
    trip=create_graph(lambda:model).invoke({'user_requirements':REQUEST},{'recursion_limit':1000})['trip_plan']
    assert model.invoke.call_count==1
    model.bind_tools.assert_not_called()
    sleep.assert_not_called()
    assert trip['metadata']['planning_status']=='FAILED'
    assert len(trip['days'])==4
    assert any('daily quota' in warning.lower() for warning in trip['warnings'])
    assert not trip['tool_trace']


def test_failed_streamlit_result_not_shown_as_ready_or_free(monkeypatch):
    from streamlit.testing.v1 import AppTest
    def missing(): raise ValueError('Model unavailable')
    trip=create_graph(missing).invoke({'user_requirements':REQUEST},{'recursion_limit':1000})['trip_plan']
    response=Mock(status_code=200); response.json.return_value={'status':'success','data':trip}
    monkeypatch.setattr('requests.post',Mock(return_value=response))
    app_test=AppTest.from_file('app.py').run(timeout=20)
    app_test.text_input[0].set_value('Vijayawada')
    app_test.text_input[1].set_value('Vizag')
    app_test.button[0].click().run(timeout=20)
    assert not app_test.exception
    assert not app_test.success
    assert any('No itinerary was generated' in item.value for item in app_test.error)
    assert all(metric.value=='Unavailable' for metric in app_test.metric if 'subtotal' in metric.label.lower())

def test_bus_is_not_a_supported_transport_mode():
    with pytest.raises(ValueError):
        TravelRequest.model_validate({**REQUEST,'transport_mode':'Bus'})
    from streamlit.testing.v1 import AppTest
    app_test=AppTest.from_file('app.py').run(timeout=20)
    transport=next(widget for widget in app_test.selectbox if 'Transport Mode' in widget.label)
    assert transport.options==['Flight','Train']


def test_four_train_fares_taxes_and_party_totals():
    from tools.estimators import estimate_train_fares
    result=estimate_train_fares({'success':True,'distance_km':600,'source_type':'USER_PROVIDED'},passengers=2)
    fares={f['class']:f for f in result['fares']}
    assert [fares[code]['base_fare'] for code in ('SL','3A','2A','1A')]==[360,720,1080,1440]
    assert [fares[code]['tax'] for code in ('SL','3A','2A','1A')]==[0,36,54,72]
    assert result['price']==1512
    assert result['source_type']=='CONFIGURED_ESTIMATE'
    assert all(f['total_fare']>0 for f in result['fares'])


def test_missing_distance_and_local_routes_no_fares(monkeypatch):
    import tools.estimators as estimators
    lookup=Mock(return_value=estimators.unavailable('Distance unavailable'))
    monkeypatch.setattr(estimators,'calculate_distance',lookup)
    assert not estimators.search_train_transport('Bangalore','Goa')['success']
    for route in [('Goa','Baga Beach'),('Goa','Old Goa'),('Airport','Hotel')]:
        before=lookup.call_count
        result=estimators.search_train_transport(*route)
        assert not result['success'] and result['price'] is None and not result['fares']
        assert lookup.call_count==before


def test_duckduckgo_distance_accepts_rail_rejects_road_and_other_routes(monkeypatch):
    import tools.estimators as estimators
    row={'title':'Vijayawada to Visakhapatnam trains','body':'Railway route distance: 350 km.','href':'https://indiarailinfo.com/search/29/401'}
    search=Mock(return_value=[row]); monkeypatch.setattr(estimators,'railway_search_results',search)
    monkeypatch.delenv('RAIL_DISTANCE_URL',raising=False)
    result=estimators.calculate_distance('Vijayawada','Vizag')
    assert result['distance_km']==350 and result['source']==row['href']
    for changes in ({'body':'Road distance: 350 km.'},{'title':'Delhi to Mumbai trains'},{'href':'https://example.com/unknown'},{'body':'Distance: 350 km. Distance: 900 km.'}):
        assert estimators.distance_from_search_result({**row,**changes},'Vijayawada','Vizag') is None


def test_train_end_to_end_leg_cache_and_no_local_costs(providers,monkeypatch):
    import tools.estimators as estimators
    train=Mock(wraps=estimators.search_train_transport)
    monkeypatch.setattr(workflow,'search_train_transport',train)
    result=run(req={**REQUEST,'transport_mode':'Train','rail_distance_km':600,'day_locations':['Goa','Baga Beach','Old Goa','Goa']})['trip_plan']
    assert [(l['origin'],l['destination']) for l in result['transport']]==[('BLR','Goa'),('Goa','BLR')]
    assert train.call_count==2
    assert providers[1].call_count==0
    assert all(len(l['result']['fares'])==4 for l in result['transport'])
    assert result['budget']['transport']==3024
    assert result['budget']['component_provenance']['transport']=='CONFIGURED_ESTIMATE'
    assert all(e['category']!='local_transport' for e in result['budget']['entries'])
    assert 'local_transport' not in result['budget']['breakdown']
    assert any(t['tool']=='search_transport' and t['cached'] for t in result['tool_trace'])


def test_arbitrary_local_transport_call_cannot_reach_distance_service(providers,monkeypatch):
    state=workflow.validate_request({'user_requirements':{**REQUEST,'transport_mode':'Train','rail_distance_km':600}})
    state.update(workflow.create_trip_blueprint(state,lambda:ScriptedModel()))
    state.update(workflow.initialize_day(state))
    spy=Mock(); monkeypatch.setattr(workflow,'search_train_transport',spy)
    state['messages'].append(AIMessage(content='',tool_calls=[{'id':'local','name':'search_transport','args':{'leg_id':'leg-1','origin':'Goa','destination':'Baga Beach'}}]))
    result=workflow.execute_tools_node(state)
    spy.assert_not_called()
    assert not json.loads(result['messages'][-1].content)['success']


def test_train_requires_user_distance():
    from schemas.travel import TravelRequest
    with pytest.raises(ValueError, match='one-way'):
        TravelRequest(**{**REQUEST, 'transport_mode': 'Train'})
    assert TravelRequest(**{**REQUEST, 'transport_mode': 'Train', 'rail_distance_km': 600}).rail_distance_km == 600


def test_train_sidebar_waits_for_distance():
    from streamlit.testing.v1 import AppTest
    app_test = AppTest.from_file('app.py').run(timeout=20)
    next(s for s in app_test.selectbox if 'Transport Mode' in s.label).select('Train').run()
    assert not app_test.exception
    assert app_test.button[0].disabled
    distance = next(n for n in app_test.number_input if 'railway distance' in n.label)
    assert distance.value is None
    distance.set_value(600.0).run()
    assert not app_test.exception
    assert not app_test.button[0].disabled

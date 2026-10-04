"""LangGraph day progression with native LangChain tool calls and factual output."""
import json
import logging
import time
from groq import RateLimitError
import os
import random
from datetime import date, timedelta
from typing import TypedDict, Any
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from schemas.travel import TravelRequest, DayPlan, TripPlan
from services.weather_service import get_live_weather
from services.flight_service import search_ignav_flights
from services.hotel_service import search_stay_hotels
from services.wikipedia_service import search_wikipedia_places, search_wikipedia_food
from utils.budget import calculate_budget, parse_budget
from tools.estimators import search_train_transport, is_local_mobility

load_dotenv()
MAX_TOOL_ROUNDS = 8

@tool
def get_weather(location: str, date: str) -> dict:
    """Get real weather for the exact itinerary date and location."""
    return get_live_weather(location, date)

@tool
def search_transport(leg_id: str) -> dict:
    """Search only a requested inter-city leg by its blueprint ID. Train uses sourced distance and configured fares; Flight uses Ignav. Executor supplies exact route/date/travelers."""
    raise RuntimeError('Use the request-scoped LangGraph executor')

@tool
def search_stay(stay_id: str) -> dict:
    """Search accommodation by blueprint stay-period ID, never by individual day."""
    raise RuntimeError('Use the request-scoped LangGraph executor')

@tool
def search_wikipedia(query: str, category: str = 'places') -> dict:
    """Find famous attractions, history, temples or local dishes. category is places or food."""
    raise RuntimeError('Use the request-scoped LangGraph executor')

@tool
def random_choice(candidate_ids: list[str], count: int = 1) -> dict:
    """Select from candidate IDs already returned by Wikipedia this day. No invented candidates."""
    raise RuntimeError('Use the request-scoped LangGraph executor')

TOOLS = {t.name: t for t in [get_weather, search_transport, search_stay, search_wikipedia, random_choice]}
TOOL_MAP = TOOLS

class TravelState(TypedDict, total=False):
    user_requirements: dict
    blueprint: dict
    transport_legs: list
    stay_periods: list
    current_day: int
    current_date: str
    current_location: str
    total_days: int
    daily_plans: list
    messages: list
    observations: list
    candidate_registry: dict
    tool_trace: list
    agent_activity: list
    warnings: list
    random_seed: int
    random_decisions: list
    tool_rounds: int
    model_pause_reason: str | None
    budget_breakdown: dict
    total_cost: float
    trip_plan: dict


def unavailable(reason):
    return {'success': False, 'status': 'UNAVAILABLE', 'source_type': 'UNAVAILABLE', 'reason': reason}


def parse_json(content):
    text = str(content).strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0]
    return json.loads(text)


def create_model():
    if not os.getenv('GROQ_API_KEY'):
        raise ValueError('GROQ_API_KEY is not configured')
    return ChatGroq(model=os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b'), temperature=0, max_tokens=1600, timeout=45, max_retries=0)


def is_daily_quota_error(exc):
    body = getattr(exc, 'body', {}) or {}
    error = body.get('error', {}) if isinstance(body, dict) else {}
    message = str(error.get('message', '')).lower() if isinstance(error, dict) else ''
    return isinstance(exc, RateLimitError) and ('tokens per day' in message or 'requests per day' in message)


def model_failure_reason(exc):
    if is_daily_quota_error(exc):
        return 'Groq daily quota reached. Wait for quota to replenish or configure a model/account with available quota.'
    if isinstance(exc, RateLimitError):
        return 'Groq rate limit reached. Wait before submitting another request.'
    return f'Planning model unavailable ({type(exc).__name__}).'


def invoke_model(model, messages):
    """Retry the same request on transient provider throttling; never restart planning."""
    for attempt in range(3):
        try:
            return model.invoke(messages)
        except RateLimitError as exc:
            if is_daily_quota_error(exc) or attempt == 2:
                raise
            headers = getattr(getattr(exc, "response", None), "headers", {})
            try:
                delay = float(headers.get("retry-after", "30"))
            except (ValueError, TypeError):
                delay = 30
            if delay > 59:
                raise
            time.sleep(max(1, delay) + 0.2)


def validate_request(state):
    req = TravelRequest.model_validate(state['user_requirements']).model_dump(mode='json')
    return {'user_requirements': req, 'total_days': (date.fromisoformat(req['end_date'])-date.fromisoformat(req['start_date'])).days+1,
            'current_day': 1, 'daily_plans': [], 'warnings': [], 'tool_trace': [], 'agent_activity': [],
            'random_seed': req['random_seed'], 'random_decisions': [], 'model_pause_reason': None}


def create_trip_blueprint(state, model_factory=create_model):
    req = state['user_requirements']
    locations = req.get('day_locations') or [req['destination']] * state['total_days']
    themes = ['Explore verified destination knowledge'] * state['total_days']
    warnings = list(state['warnings'])
    pause_reason = state.get('model_pause_reason')
    try:
        response = invoke_model(model_factory(), [
            SystemMessage(content='Create a travel blueprint, not factual claims. Return JSON {"days":[{"location":"...","theme":"..."}]}. Exactly one entry per inclusive day. Keep accommodation/day base location at the destination unless the user supplies day_locations. Do not invent sights, hotels, prices or transport.'),
            HumanMessage(content=json.dumps(req))])
        outline = parse_json(response.content)['days']
        if len(outline) != state['total_days']:
            raise ValueError('Blueprint length')
        themes = [str(d.get('theme', themes[i])) for i,d in enumerate(outline)]
    except Exception as exc:
        if is_daily_quota_error(exc):
            pause_reason = model_failure_reason(exc)
            warnings.append(pause_reason)
        warnings.append('Blueprint model unavailable or invalid; using requested dates and destination base.')
    days = [{'day': i+1, 'date': (date.fromisoformat(req['start_date'])+timedelta(days=i)).isoformat(), 'location': loc, 'theme': themes[i]} for i,loc in enumerate(locations)]
    legs = []
    route = [(req['source_city'], req['destination'], req['start_date']), (req['destination'], req['source_city'], req['end_date'])]
    for origin,destination,dep in route:
        if not is_local_mobility(origin, destination):
            legs.append({'id': f'leg-{len(legs)+1}', 'origin': origin, 'destination': destination, 'departure_date': dep, 'mode': req['transport_mode']})
    stays = []
    for day in days[:-1]:
        if stays and stays[-1]['location'] == day['location']:
            stays[-1]['check_out'] = (date.fromisoformat(day['date'])+timedelta(days=1)).isoformat()
            stays[-1]['nights'] += 1
        else:
            stays.append({'id': f'stay-{len(stays)+1}', 'location': day['location'], 'check_in': day['date'], 'check_out': (date.fromisoformat(day['date'])+timedelta(days=1)).isoformat(), 'nights': 1})
    return {'blueprint': {'days': days}, 'transport_legs': legs, 'stay_periods': stays, 'warnings': warnings, 'model_pause_reason': pause_reason}


def initialize_day(state):
    day = state['blueprint']['days'][state['current_day']-1]
    context = {**day, 'request': state['user_requirements'], 'transport_legs': [{k:v for k,v in x.items() if k!='result'} | {'searched': 'result' in x} for x in state['transport_legs']], 'stay_periods': [{k:v for k,v in x.items() if k!='result'} | {'searched': 'result' in x} for x in state['stay_periods']]}
    prompt = '''Use native tools for all factual information. Use Wikipedia for famous places, historical/cultural sites, temples and famous/local food. Query weather with the exact current date/location. Search each needed transport leg and stay period by ID, reuse existing results. search_transport is only for the requested source-to-destination and return inter-city legs. Never request airport-to-hotel, hotel-to-beach, beach-to-temple or local taxi/auto mobility fares. Daily sightseeing must not trigger transport searches. Train fares are deterministic configured estimates from sourced railway distance; Flight uses Ignav. Use search_transport on each unsearched leg when transport information is needed. Never invent train distance, fares or availability. You may call multiple tools and further tools after results. A small set of sourced attractions and dishes is sufficient. Do not exhaustively research or repeat successful knowledge queries. Once enough information exists, finalize the schedule. random_choice selects existing candidate IDs only. When ready return JSON {"morning":["candidate-id"],"afternoon":["candidate-id"],"evening":["candidate-id"],"places":["candidate-id"],"food":["candidate-id"],"temples":["candidate-id"]}. Use only returned IDs, no factual free text, no invented costs/weather/hours/availability. Plan each day once.'''
    return {'current_date': day['date'], 'current_location': day['location'], 'observations': [], 'candidate_registry': {}, 'tool_rounds': 0,
            'messages': [SystemMessage(content=prompt), HumanMessage(content=json.dumps(context))]}


def planner_decides_tools(state, model_factory=create_model):
    messages = list(state['messages'])
    warnings = list(state['warnings'])
    pause_reason = state.get('model_pause_reason')
    if pause_reason:
        warnings.append(f"Day {state['current_day']}: {pause_reason} No itinerary generated.")
        return {'messages': messages + [AIMessage(content='{}')], 'warnings': warnings}
    try:
        model = model_factory()
        if state['tool_rounds'] >= MAX_TOOL_ROUNDS:
            messages.append(HumanMessage(content='The research safety ceiling is reached. Return the final schedule JSON using only candidate IDs already in ToolMessages. Do not request more tools.'))
            bound = model.bind(response_format={'type': 'json_object'}) if hasattr(model, 'bind') else model
        else:
            bound = model.bind_tools(list(TOOLS.values()))
        response = invoke_model(bound, messages)
    except Exception as exc:
        logging.getLogger(__name__).warning('LLM invocation failed (%s)', type(exc).__name__)
        response = AIMessage(content='{}')
        reason = model_failure_reason(exc)
        if is_daily_quota_error(exc):
            pause_reason = reason
        warnings.append(f"Day {state['current_day']}: {reason} No unverified itinerary generated.")
    return {'messages': messages+[response], 'warnings': warnings, 'model_pause_reason': pause_reason}


def execute_tools_node(state):
    messages = list(state['messages'])
    observations = list(state['observations'])
    registry = dict(state['candidate_registry'])
    legs = [dict(x) for x in state['transport_legs']]
    stays = [dict(x) for x in state['stay_periods']]
    decisions = list(state['random_decisions'])
    trace, warnings, activity = list(state['tool_trace']), list(state['warnings']), list(state['agent_activity'])
    req = state['user_requirements']
    for call in messages[-1].tool_calls:
        name, args = call['name'], call['args']
        cached = False
        try:
            if state['tool_rounds'] >= MAX_TOOL_ROUNDS:
                result = unavailable('Tool loop safety ceiling reached')
            elif name == 'get_weather':
                if args != {'location': state['current_location'], 'date': state['current_date']}:
                    result = unavailable('Weather arguments must match current day date and location')
                else:
                    prior = next((o['result'] for o in observations if o['tool']==name and o['args']==args), None)
                    cached = prior is not None
                    result = prior if cached else get_live_weather(**args)
            elif name in ('search_transport', 'search_stay'):
                records = legs if name=='search_transport' else stays
                key = 'leg_id' if name=='search_transport' else 'stay_id'
                if set(args) != {key}:
                    raise ValueError('Only blueprint ID arguments are accepted; local routes are forbidden')
                record = next(x for x in records if x['id']==args[key])
                cached = 'result' in record
                if cached:
                    result = record['result']
                elif name=='search_transport':
                    result = search_ignav_flights(record['origin'], record['destination'], departure_date=record['departure_date'], passengers=req['passengers']) if record['mode']=='Flight' else search_train_transport(record['origin'], record['destination'], passengers=req['passengers'], selected_class=req['train_class'], supplied_distance=req.get('rail_distance_km'))
                else:
                    result = search_stay_hotels(record['location'], record['check_in'], record['check_out'], req['passengers'], req['hotel_type'])
                record['result'] = result
            elif name=='search_wikipedia':
                category = args.get('category', 'places')
                if category not in ('places','food'):
                    raise ValueError('Invalid category')
                fn = search_wikipedia_food if category=='food' else search_wikipedia_places
                result = fn(state['current_location'], args['query'])
                key = 'food_items' if category=='food' else 'places'
                result[key] = [dict(x) for x in result.get(key, [])]
                for item in result[key]:
                    candidate_id = f"d{state['current_day']}-{category}-{len(registry)+1}"
                    item['candidate_id'] = candidate_id
                    item['kind'] = category
                    registry[candidate_id] = item
            elif name=='random_choice':
                ids = args['candidate_ids']
                count = args.get('count',1)
                if len(set(ids)) != len(ids) or not all(x in registry for x in ids) or not isinstance(count,int) or not 0 <= count <= len(ids):
                    raise ValueError('Random choice requires unique verified candidate IDs and valid count')
                rng = random.Random(f"{state['random_seed']}:{len(decisions)}")
                selected = rng.sample(ids, count)
                decisions.append({'day': state['current_day'], 'candidates': ids, 'selected': selected})
                result = {'success': True, 'status': 'SUCCESS', 'selected': [registry[x] for x in selected]}
            else:
                result = unavailable('Unknown tool')
        except Exception:
            result = unavailable(f'{name} failed or received invalid arguments')
        success = result.get('success', str(result.get('status','')).lower()=='success')
        for provider_warning in result.get('warnings', []):
            warnings.append(f"Day {state['current_day']} {name}: {provider_warning}")
        if not success:
            reason = result.get('reason') or result.get('message') or result.get('error',{}).get('message') or 'Data unavailable'
            warnings.append(f"Day {state['current_day']} {name}: {reason}")
        model_result = {k:v for k,v in result.items() if k not in ('itineraries','available_flights','hotels','segments','raw_price')}
        messages.append(ToolMessage(content=json.dumps(model_result), tool_call_id=call['id'], name=name))
        observation = {'day': state['current_day'], 'date': state['current_date'], 'location': state['current_location'], 'tool': name, 'args': args, 'result': result, 'cached': cached}
        observations.append(observation)
        trace.append(observation)
        activity.append(f"Day {state['current_day']} {name}: {'cached' if cached else ('available' if success else 'unavailable')}")
    return {'messages': messages, 'observations': observations, 'candidate_registry': registry, 'transport_legs': legs,
            'stay_periods': stays, 'random_decisions': decisions, 'tool_trace': trace, 'warnings': warnings,
            'agent_activity': activity, 'tool_rounds': state['tool_rounds']+1}


def build_daily_plan(state):
    registry = state['candidate_registry']
    warnings = [x for x in state['warnings'] if x.startswith(f"Day {state['current_day']} ") or x.startswith(f"Day {state['current_day']}:")]
    try:
        if not isinstance(state['messages'][-1], AIMessage) or getattr(state['messages'][-1], 'tool_calls', []):
            raise ValueError('No final model synthesis')
        synthesis = parse_json(state['messages'][-1].content)
        if not isinstance(synthesis, dict):
            raise ValueError('Expected JSON object')
    except Exception:
        synthesis = {}
        warnings.append('Structured day synthesis unavailable; showing retrieved candidates only.')
    def resolve(key, kind=None):
        values = synthesis.get(key, [])
        if not isinstance(values,list):
            return []
        if any(not isinstance(x,str) or x not in registry for x in values):
            warnings.append(f'Unverified {key} references discarded.')
        return [registry[x] for x in dict.fromkeys(x for x in values if isinstance(x,str) and x in registry) if kind is None or registry[x]['kind']==kind]
    weather = next((o['result'] for o in reversed(state['observations']) if o['tool']=='get_weather'), None)
    if not weather or not weather.get('success'):
        warnings.append('Weather data unavailable; verify conditions before travel.')
    stay = next((s.get('result') for s in state['stay_periods'] if s['check_in'] <= state['current_date'] < s['check_out']), None)
    places = resolve('places','places') or [x for x in registry.values() if x['kind']=='places']
    food = resolve('food','food') or [x for x in registry.values() if x['kind']=='food']
    record = DayPlan(day=state['current_day'], date=state['current_date'], location=state['current_location'], weather=weather,
        hotel=stay, places=places, food=food, temples=resolve('temples','places'), activities=resolve('morning')+resolve('afternoon')+resolve('evening'),
        morning=resolve('morning'), afternoon=resolve('afternoon'), evening=resolve('evening'), warnings=list(dict.fromkeys(warnings)),
        notes=['Wikipedia is destination knowledge, not current opening hours or restaurant availability.'],
        summary=f"Day {state['current_day']} in {state['current_location']}").model_dump()
    return {'daily_plans': state['daily_plans']+[record]}


def finalize_trip(state):
    budget = calculate_budget(state)
    warnings = list(dict.fromkeys(state['warnings']+[w for d in state['daily_plans'] for w in d['warnings']]))
    if not budget['complete']:
        warnings.append('Budget is partial: known subtotal excludes unavailable costs; budget compliance cannot be confirmed.')
    if budget['status']=='OVER_BUDGET':
        warnings.append('Known costs exceed the requested budget.')
    for item in state['transport_legs']+state['stay_periods']:
        if 'result' not in item:
            warnings.append(f"{item['id']} was not searched by the model; information unavailable.")
    scheduled_days = sum(any(day.get(slot) for slot in ('morning', 'afternoon', 'evening')) for day in state['daily_plans'])
    planning_status = 'FAILED' if not scheduled_days else ('PARTIAL' if warnings or scheduled_days < state['total_days'] else 'COMPLETE')
    plan = TripPlan(metadata={**state['user_requirements'], 'total_days': state['total_days'], 'planning_status': planning_status},
        transport=state['transport_legs'], accommodation=state['stay_periods'], days=state['daily_plans'], budget=budget,
        randomization={'seed': state['random_seed'], 'decisions': state['random_decisions']}, warnings=warnings, tool_trace=state['tool_trace']).model_dump()
    return {'trip_plan': plan, 'budget_breakdown': budget, 'total_cost': budget['total'], 'warnings': warnings}


def create_graph(model_factory=create_model):
    builder = StateGraph(TravelState)
    builder.add_node('validate_request', validate_request)
    builder.add_node('create_trip_blueprint', lambda s: create_trip_blueprint(s, model_factory))
    builder.add_node('initialize_day', initialize_day)
    builder.add_node('llm', lambda s: planner_decides_tools(s, model_factory))
    builder.add_node('execute_tools', execute_tools_node)
    builder.add_node('build_day_plan', build_daily_plan)
    builder.add_node('next_day', lambda s: {'current_day': s['current_day']+1})
    builder.add_node('finalize_trip', finalize_trip)
    builder.add_edge(START, 'validate_request')
    builder.add_edge('validate_request', 'create_trip_blueprint')
    builder.add_edge('create_trip_blueprint', 'initialize_day')
    builder.add_edge('initialize_day', 'llm')
    builder.add_conditional_edges('llm', lambda s: 'tools' if getattr(s['messages'][-1], 'tool_calls', []) else 'done', {'tools': 'execute_tools', 'done': 'build_day_plan'})
    builder.add_conditional_edges('execute_tools', lambda s: 'done' if s['tool_rounds']>MAX_TOOL_ROUNDS else 'llm', {'done': 'build_day_plan', 'llm':'llm'})
    builder.add_conditional_edges('build_day_plan', lambda s: 'more' if s['current_day']<s['total_days'] else 'done', {'more':'next_day','done':'finalize_trip'})
    builder.add_edge('next_day','initialize_day')
    builder.add_edge('finalize_trip',END)
    return builder.compile()

graph = create_graph()

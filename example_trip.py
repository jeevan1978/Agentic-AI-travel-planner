"""Run the production graph; unavailable providers remain explicit in the saved result."""
import json
from pathlib import Path
from graph import graph

request = {'source_city':'Bangalore','destination':'Goa','start_date':'2026-10-10','end_date':'2026-10-13','passengers':2,'budget':'30000 INR','transport_mode':'Flight','interests':['Beaches','Temples','Seafood','Sightseeing'],'random_seed':17}
if __name__ == '__main__':
    result = None
    for update in graph.stream({'user_requirements':request},{'recursion_limit':1000}):
        for node, values in update.items():
            if node == 'build_day_plan':
                print(f"Completed day {values['daily_plans'][-1]['day']}", flush=True)
            elif node == 'execute_tools':
                print(f"Tool observations recorded: {len(values['tool_trace'])}", flush=True)
            elif node == 'finalize_trip':
                result = values['trip_plan']
    output = Path('output/example_trip.json')
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'days':len(result['days']),'tool_calls':len(result['tool_trace']),'budget_status':result['budget']['status'],'known_subtotal':result['budget']['known_subtotal'],'warnings':result['warnings'],'output':str(output.resolve())},ensure_ascii=True,indent=2))

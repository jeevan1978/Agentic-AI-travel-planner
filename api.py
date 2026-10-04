"""FastAPI entry point for the existing Travel Planner."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from graph import graph
from schemas.travel import TravelRequest, APIResponse

app = FastAPI(title='VoyageAI Travel Planner', version='2.0.0')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173','http://localhost:8501'], allow_methods=['*'], allow_headers=['*'])

@app.get('/')
def root():
    return {'message':'Travel Planner running; API documentation at /docs'}

@app.post('/plan-trip', response_model=APIResponse)
@app.post('/api/plan', response_model=APIResponse)
def plan_trip(request: TravelRequest):
    try:
        result = graph.invoke({'user_requirements':request.model_dump(mode='json')}, config={'recursion_limit':1000})
        return {'status':'success', 'data':result['trip_plan']}
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500,detail='Planning failed; check backend logs and configuration')

if __name__=='__main__':
    import uvicorn
    uvicorn.run('api:app',host='127.0.0.1',port=8080)

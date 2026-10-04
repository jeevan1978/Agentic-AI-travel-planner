# Architecture and agentic workflow

These diagrams describe the implemented functions in `graph.py`. Mermaid renders in compatible Markdown viewers. The UML state, sequence and class diagrams remain editable as text.

## Architecture overview

This overview uses the reference's top-to-bottom layout, rectangular boxes, curved connections and a decision diamond. Tool branches represent available choices, not a mandatory sequence. The LLM decides which tools to call.

```mermaid
%%{init: {"theme": "dark", "flowchart": {"curve": "basis", "nodeSpacing": 35, "rankSpacing": 45}}}%%
flowchart TD
    User["👤 User"] --> UI["🗺️ Streamlit / React interface"]
    UI --> Request["Request validation<br/>Route · dates · travelers · interests · budget<br/>Train requires one-way railway distance"]
    Request --> Agent["🧠 LangGraph Travel Agent"]
    Agent --> Blueprint["Trip blueprint<br/>Exact dates and daily locations<br/>Outbound / return legs · stay periods"]
    Blueprint --> Day["📅 Initialize current day<br/>Fresh messages and candidate registry"]
    Day --> LLM["LangChain + Groq LLM<br/>Reason and choose native tool calls"]
    LLM --> Executor["Request-scoped tool executor<br/>Validate arguments · reuse cached results"]
    Executor --> Flight["✈️ Flight tool<br/>Inter-city leg ID only"]
    Executor --> Stay["🏨 Accommodation tool<br/>Stay-period ID only"]
    Executor --> Weather["🌦️ Weather tool<br/>Exact day date and location"]
    Executor --> Wiki["📚 Wikipedia tool<br/>Places · culture · temples · dishes"]
    Executor --> Train["🚆 Train estimator<br/>User-provided one-way railway distance"]
    Executor --> Random["🎲 Seeded selection<br/>Existing day candidate IDs only"]
    Flight --> Ignav["Ignav API<br/>Provider flight quotes"]
    Stay --> StayAPI["StayingAPI<br/>Live accommodation results"]
    Weather --> WeatherAPI["OpenWeather API<br/>Available exact-date forecasts"]
    Wiki --> MediaWiki["Wikipedia / MediaWiki<br/>Sourced knowledge and URLs"]
    Train --> Fares["Deterministic Python fare calculation<br/>SL · 3A · 2A · 1A<br/>Configured rates and taxes"]
    Ignav --> Results["Tool results and provenance<br/>Failures remain unavailable with warnings"]
    StayAPI --> Results
    WeatherAPI --> Results
    MediaWiki --> Results
    Fares --> Results
    Random --> Results
    Results --> Message["🔄 Matching ToolMessage<br/>Return observations to the LLM"]
    Message --> LLM
    LLM -->|Final schedule JSON| Plan["Build daily plan<br/>Resolve verified candidate IDs only"]
    Plan --> More{"More trip days?"}
    More -->|Yes: advance day| Day
    More -->|No| Budget["💰 Python Decimal budget<br/>Known costs · missing prices · provenance"]
    Budget --> Final["Final TripPlan<br/>COMPLETE / PARTIAL / FAILED<br/>Warnings · tool trace · selection audit"]
    Final --> Display["📋 Display itinerary and budget status"]
    classDef box fill:#222222,stroke:#999999,color:#ffffff,stroke-width:1px;
    class User,UI,Request,Agent,Blueprint,Day,LLM,Executor,Flight,Stay,Weather,Wiki,Train,Random,Ignav,StayAPI,WeatherAPI,MediaWiki,Fares,Results,Message,Plan,More,Budget,Final,Display box;
```

Only the tool-observation loop and forward day progression loop return to earlier nodes. There is no budget-driven replanning, Bus estimator or local mobility costing.

## LangGraph state diagram

```mermaid
stateDiagram-v2
    [*] --> validate_request
    validate_request --> create_trip_blueprint: valid request
    create_trip_blueprint --> initialize_day
    initialize_day --> llm
    llm --> execute_tools: AIMessage has tool_calls
    execute_tools --> llm: append ToolMessages and reason again
    llm --> build_day_plan: final AIMessage without tool_calls
    execute_tools --> build_day_plan: safety ceiling exceeded
    build_day_plan --> next_day: current_day < total_days
    next_day --> initialize_day: increment day
    build_day_plan --> finalize_trip: final day
    finalize_trip --> [*]
    note right of validate_request
        Train requires positive user distance.
        Invalid requests return HTTP 422.
    end note
    note right of initialize_day
        Set exact date and location.
        Reset day messages, observations,
        candidates and tool rounds.
    end note
    note right of finalize_trip
        Decimal budget arithmetic.
        Assemble TripPlan and warnings.
        No replanning edge.
    end note
```

The blueprint LLM supplies themes only. Python establishes inclusive dates, requested day locations, outward/return legs and consecutive stay periods. Blueprint model failure leaves a requested-date skeleton; it does not invent a replacement schedule.

`MAX_TOOL_ROUNDS = 8` is a safety ceiling. At the ceiling the model is asked for final structured output without new tools. An executor guard prevents further research if the model still emits tool calls. It does not impose a fixed tool order.

## LLM/tool sequence diagram

```mermaid
sequenceDiagram
    actor User
    participant UI as Streamlit or React
    participant API as FastAPI
    participant Graph as LangGraph
    participant LLM as LangChain / Groq
    participant Exec as Request-scoped executor
    participant Provider as Wikipedia / Weather / Ignav / Stay
    participant Train as Python estimator
    User->>UI: route, dates, travelers, interests, budget
    opt Train selected
        UI->>User: ask one-way railway distance and class
        User->>UI: positive distance in km
    end
    UI->>API: POST /api/plan
    API->>API: validate TravelRequest
    API->>Graph: invoke request state
    Graph->>LLM: blueprint themes request
    LLM-->>Graph: theme JSON or failure
    Graph->>Graph: exact days, two inter-city legs, stay periods
    loop Each inclusive calendar day
        Graph->>Graph: initialize exact date/location and fresh day context
        loop Research until final synthesis or safety ceiling
            Graph->>LLM: messages and native tool schemas
            LLM-->>Graph: AIMessage with tool_calls or final JSON
            opt AIMessage has tool_calls
                Graph->>Exec: execute requested calls
                alt Cached transport leg or stay period
                    Exec->>Exec: reuse request-scoped result
                else Train leg
                    Exec->>Train: supplied distance, class, passengers
                    Train-->>Exec: four estimates and provenance
                else Weather, Flight, Stay or Wikipedia
                    Exec->>Provider: validated route, period, date or query
                    Provider-->>Exec: data or unavailable response
                else random_choice
                    Exec->>Exec: seeded sample of day candidate IDs
                end
                Exec-->>Graph: matching ToolMessage with tool_call_id
                Note over Graph,LLM: Next invocation includes observations for further reasoning.
            end
        end
        Graph->>Graph: resolve verified candidate IDs into DayPlan
    end
    Graph->>Graph: Decimal budget, missing costs and TripPlan
    Graph-->>API: trip_plan
    API-->>UI: envelope, statuses and warnings
    UI-->>User: itinerary and partial budget
```

LangChain exposes native tool schemas. The executor dispatches model-requested calls and validates arguments; it does not choose a research sequence. Provider failures also become ToolMessages. Unsearched legs/stays are explicitly unavailable at finalization.

## Class and state diagram

```mermaid
classDiagram
    class TravelRequest {
        str source_city
        str destination
        date start_date
        date end_date
        int passengers
        str transport_mode
        str train_class
        float rail_distance_km
        int random_seed
        list day_locations
    }
    class TravelState {
        dict user_requirements
        dict blueprint
        list transport_legs
        list stay_periods
        int current_day
        str current_date
        str current_location
        list messages
        list observations
        dict candidate_registry
        list daily_plans
        list tool_trace
        list random_decisions
        str model_pause_reason
    }
    class DayPlan {
        int day
        str date
        str location
        dict weather
        dict hotel
        list morning
        list afternoon
        list evening
        list places
        list food
        list warnings
    }
    class TripPlan {
        dict metadata
        list transport
        list accommodation
        list days
        dict budget
        dict randomization
        list warnings
        list tool_trace
    }
    class APIResponse {
        str status
        TripPlan data
    }
    TravelRequest --> TravelState : validated into
    TravelState --> DayPlan : builds per day
    TripPlan *-- DayPlan : days
    TravelState --> TripPlan : finalizes
    APIResponse *-- TripPlan : data
```

`TravelState` is a TypedDict; request/response types are Pydantic models. The diagram lists principal fields. `schemas/travel.py` and `graph.py` provide the full contracts.

## State ownership and factual boundaries

| Scope | State and behavior |
| --- | --- |
| Entire trip | Request, blueprint, leg/stay results, completed days, trace, warnings retained during forward progression |
| Current day | Date/location, messages, observations, candidates and tool rounds initialized afresh |
| Transport | Only outward/return leg IDs; repeat lookup reuses cached result |
| Accommodation | Consecutive nights grouped; checkout excluded; cache by stay ID |
| Random selection | Seed and decision counter select existing day candidate IDs |

Weather arguments must equal the current date/location. Transport and stay calls accept only blueprint IDs. Wikipedia results receive day-scoped IDs. Final schedule JSON can reference only those IDs; invented references are discarded.

Normal Train requests use user distance, marked `USER_PROVIDED`. Python estimates are marked `CONFIGURED_ESTIMATE`. Flight/hotel costs retain provider provenance. Food/activity prices are unavailable; local mobility is excluded.

Daily Groq quota exhaustion sets `model_pause_reason`, stopping further model calls for this request. Transient limits permit bounded retries of the same invocation. Neither behavior restarts completed days or replans the trip.

## Implementation map

| Component | Implementation |
| --- | --- |
| Graph nodes and edges | `graph.py` |
| API/validation | `api.py`, `schemas/travel.py` |
| Tool schemas/dispatch | `graph.py`: `TOOLS`, `execute_tools_node` |
| Flights | `services/flight_service.py`, `services/ignav_service.py` |
| Weather | `services/weather_service.py` |
| Accommodation | `services/hotel_service.py` |
| Places/dishes | `services/wikipedia_service.py` |
| Train arithmetic | `tools/estimators.py`, `config/transport_rates.json` |
| Budget | `utils/budget.py` |

Hotel type is passed into the service but currently does not enforce a star-category filter. Fare selection uses the lowest eligible INR flight quote, lowest eligible INR hotel total, or the user's train class. Preferences do not guarantee matching provider inventory.

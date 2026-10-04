# ✈️ Agentic AI Travel Planner

An **agentic AI travel planning system** built with **LangGraph, LangChain, Groq LLM, and external data tools**.

The system accepts a user's travel request and generates a structured, day-by-day trip plan using real-world information from external services such as weather, flights, accommodation, and Wikipedia.

The planner uses an **LLM-driven tool-calling loop** rather than a fixed sequence of API calls. The LLM decides which tools are needed, receives their results, and continues reasoning until it has enough information to produce the plan.

---

## 🚀 Key Features

* 🤖 **Agentic planning with LangGraph**
* 🧠 **LLM reasoning with LangChain + Groq**
* 🔧 **Dynamic tool selection**
* 🔄 **LLM → Tool → Tool Result → LLM workflow**
* 📅 **Day-by-day itinerary generation**
* 🌤️ **Date-specific weather information**
* ✈️ **Flight search**
* 🚆 **Train fare estimation**
* 🏨 **Accommodation search**
* 📚 **Wikipedia-based destination knowledge**
* 🍛 **Famous/local food discovery through Wikipedia**
* 🎲 **Controlled random selection**
* 💰 **Deterministic budget calculation**
* ⚠️ **Graceful handling of unavailable APIs**
* 🔐 **Environment-based API configuration**
* 🧪 **Automated testing**

---

# 🏗️ Architecture

The planner follows a single-pass LangGraph workflow.
<img width="1536" height="1024" alt="Agentic AI Travel Planner Architecture" src="https://github.com/user-attachments/assets/6a9e0809-da46-4b11-84b7-e52e980cc4d6" />



# 🧠 Agentic Tool-Calling

The LLM is responsible for deciding **which tools are required**.

The application does not force a fixed tool sequence such as:

```text
Weather → Flight → Hotel → Wikipedia
```

Instead:

```text
User Request
     ↓
LLM
     ↓
Decides required tools
     ↓
LangGraph executes tools
     ↓
Tool results become ToolMessages
     ↓
LLM sees the results
     ↓
LLM may request additional tools
     ↓
Eventually produces structured output
```

This allows the planner to adapt tool usage to the actual travel request.

For example, if the user asks for:

> "3 days in Goa focused on beaches and seafood"

the LLM may request:

```text
Wikipedia → famous places
Wikipedia → local/famous food
Weather → daily weather
Stay → accommodation
Transport → source → Goa
```

It does not have to call every tool if the information is unnecessary.

---

# 🔧 Available Tools

## ✈️ Flight Search

The flight tool retrieves flight/transport information for actual travel legs.

Example:

```text
Bangalore → Goa
Goa → Bangalore
```

Flights are associated with **transport legs**, not individual itinerary days.

---

# 🚆 Train Transport

Train transport is only used for **source → destination travel**.

It is not used for local transportation inside a destination.

### Supported transport modes

```text
✈️ Flight
🚆 Train
```

Bus transportation is **not supported**.

### Train workflow

When the user selects Train:

```text
Source
   ↓
Destination
   ↓
Determine railway distance
   ↓
Calculate class-wise estimated fare
   ↓
Apply configured tax/charges
   ↓
Return all supported classes
```

### Train classes

The planner calculates estimated fares for:

| Class               | Configured Rate |
| ------------------- | --------------: |
| Sleeper (SL)        |        ₹0.60/km |
| AC 3-Tier (3A)      |        ₹1.20/km |
| AC 2-Tier (2A)      |        ₹1.80/km |
| AC First Class (1A) |        ₹2.40/km |

The calculation is deterministic:

```text
base_fare = distance_km × rate_per_km
```

Then applicable configured taxes/charges are added.

These values are treated as **configured fare estimates**, not guaranteed live Indian Railways ticket prices.

### Example

For a 600 km railway distance:

```text
Sleeper = 600 × ₹0.60 = ₹360
3A      = 600 × ₹1.20 = ₹720
2A      = 600 × ₹1.80 = ₹1,080
1A      = 600 × ₹2.40 = ₹1,440
```

Applicable taxes/charges are added separately.

### Important rules

The system must:

* never return ₹0 when valid distance information exists
* never invent railway distance
* never invent train prices
* never use randomization for distance or fares
* clearly report `UNAVAILABLE` when required railway-distance information cannot be obtained

---

# 📍 Transport Is Only Source → Destination

Transport search is only performed for actual travel legs.

Example:

```text
Bangalore → Goa       ✅
Goa → Bangalore       ✅
```

Local destination movement does not trigger transport pricing:

```text
Goa → Baga Beach       ❌
Goa → Old Goa          ❌
Hotel → Restaurant     ❌
Hotel → Beach          ❌
Airport → Hotel        ❌
```

The planner does not fabricate local transportation costs.

---

# 🌤️ Weather

Weather is requested using the **exact date and destination location for each itinerary day**.

For example:

```text
Day 1
Date: 2026-10-10
Location: Goa
        ↓
Weather API
        ↓
Day 1 weather
```

Then:

```text
Day 2
Date: 2026-10-11
Location: Goa
        ↓
Weather API
        ↓
Day 2 weather
```

Weather information from one day must not leak into another day.

If weather data is unavailable:

```text
status: unavailable
```

The system must not invent weather information.

---

# 🏨 Accommodation

Accommodation is searched for the **stay period**, rather than independently for every itinerary day.

Example:

```text
Check-in: 2026-10-10
Check-out: 2026-10-13
```

The selected accommodation can then be reused across the relevant days.

If accommodation information is unavailable, the planner should clearly report it instead of inventing a hotel or price.

---

# 📚 Wikipedia Knowledge Tool

Wikipedia is used as a destination knowledge source.

It can provide information about:

* famous places
* historical places
* cultural attractions
* landmarks
* temples
* famous/local food
* regional dishes
* destination background

For example:

```text
Destination: Goa
        ↓
Wikipedia
        ↓
Famous places
Historical attractions
Cultural attractions
Famous/local food
```

Wikipedia is **not** treated as a live restaurant booking system or live hotel/availability provider.

---

# 🎲 Random Selection

Randomization is used only as a **selector**, never as a fact generator.

For example:

```text
Wikipedia returns:

1. Fort Aguada
2. Basilica of Bom Jesus
3. Dudhsagar Falls
4. Chapora Fort
5. Palolem Beach
6. Baga Beach
7. Anjuna Beach
8. Se Cathedral

        ↓

Random selector

        ↓

Select 3 real candidates
```

The random function can select among real candidates returned by tools.

It must never create:

```text
Fake attraction
Fake restaurant
Fake hotel
Fake price
Fake weather
Fake distance
Fake availability
```

A request-scoped random seed can be stored to make selections reproducible.

Example:

```text
random_seed: 12345
```

Same seed + same candidate set should produce the same selection.

---

# 📅 Day-by-Day Planning

Each itinerary day has its own:

* day number
* date
* location
* weather
* activities
* places
* food
* temples
* notes
* warnings

Example:

```text
Day 1
Date: 2026-10-10
Location: Goa
```

```text
Day 2
Date: 2026-10-11
Location: Goa
```

The planner must correctly propagate the date and location for every day.

---

# 🧾 DayPlan Structure

Each day produces a structured `DayPlan`.

Example:

```json
{
  "day": 1,
  "date": "2026-10-10",
  "location": "Goa",
  "weather": {},
  "morning": [],
  "afternoon": [],
  "evening": [],
  "places": [],
  "food": [],
  "temples": [],
  "activities": [],
  "notes": [],
  "warnings": []
}
```

---

# 🗺️ TripPlan

The complete trip is returned as a structured `TripPlan`.

It contains:

```text
Trip metadata
Transport legs
Accommodation
Daily plans
Budget
Warnings
Randomization information
Agent/tool activity
```

Example structure:

```text
TripPlan
 ├── metadata
 ├── transport
 ├── accommodation
 ├── days
 │    ├── Day 1
 │    ├── Day 2
 │    └── Day 3
 ├── budget
 ├── randomization
 └── warnings
```

---

# 💰 Budget Calculation

Budget arithmetic is performed by deterministic Python code.

The LLM does not perform the final financial calculations.

Possible cost provenance values include:

```text
LIVE_PROVIDER
USER_PROVIDED
CONFIGURED_ESTIMATE
UNAVAILABLE
```

The system must not silently fabricate prices.

If a required price is unavailable:

```text
status = unavailable
```

and a warning should be included in the final result.

---

# ⚠️ API Failure Handling

External APIs can fail or return incomplete information.

The planner should continue whenever possible.

Example:

```text
Weather API
     ↓
Unavailable
     ↓
Tool returns:
{
  "status": "unavailable",
  "source": "weather_api",
  "message": "Weather data unavailable"
}
     ↓
LLM receives ToolMessage
     ↓
Continues planning
     ↓
Adds warning
```

The system must **not**:

* invent weather
* invent flight prices
* invent hotel prices
* invent train distance
* invent restaurant information
* restart the entire trip

---

# 🚫 No Dynamic Replanning

The planner uses a **single-pass trip planning workflow**.

It does not dynamically restart the entire itinerary when a provider fails or when a budget constraint is not satisfied.

For example:

```text
API failure
   ↓
Return unavailable result
   ↓
LLM continues using available information
   ↓
Add warning
```

It does **not** do:

```text
API failure
   ↓
Restart trip
   ↓
Replan everything
   ↓
Try again
```

This keeps the workflow predictable and easier to debug.

---

# 🧩 Canonical State

The LangGraph state contains information such as:

```text
request
trip_blueprint
current_day
current_date
current_location

transport_legs
selected_stay

day_observations
daily_plans

random_seed
random_decisions

budget
warnings

messages
agent_activity
tool_trace
```

Day-specific observations are scoped by:

```text
day
date
location
tool
```

This prevents information from one itinerary day from accidentally leaking into another.

---

# 🛠️ Technology Stack

| Technology               | Purpose                              |
| ------------------------ | ------------------------------------ |
| Python                   | Core application                     |
| LangGraph                | Agent workflow/state machine         |
| LangChain                | Tool integration and LLM interaction |
| Groq                     | LLM provider                         |
| FastAPI                  | Backend API                          |
| Streamlit                | User interface                       |
| Wikipedia                | Destination knowledge                |
| Weather API              | Weather data                         |
| Ignav                    | Flight/transport information         |
| Stay API                 | Accommodation information            |
| Open-source railway data | Railway-distance information         |
| Pydantic                 | Structured schemas                   |
| Pytest                   | Testing                              |

---

# 📁 Project Structure

A typical structure is:

```text
travel-planner/
│
├── app/
│   ├── graph.py
│   ├── state.py
│   ├── schemas.py
│   ├── tools/
│   │   ├── flight_tool.py
│   │   ├── train_tool.py
│   │   ├── weather_tool.py
│   │   ├── stay_tool.py
│   │   ├── wikipedia_tool.py
│   │   └── random_tool.py
│   │
│   ├── services/
│   └── utils/
│
├── tests/
│
├── frontend/
│
├── data/
│   └── railway/
│
├── requirements.txt
├── .env.example
└── README.md
```

The exact structure may vary depending on the implementation.

---

# 🔐 Environment Variables

API keys and secrets must never be hardcoded.

Example `.env`:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=your_groq_model

IGNAV_API_KEY=your_ignav_api_key

STAYING_API_KEY=your_stay_api_key

OPENWEATHER_API_KEY=your_openweather_api_key

RANDOM_SEED=12345
```

Use `.env.example` for documentation.

Never commit:

```text
.env
API keys
tokens
passwords
private credentials
```

---

# ▶️ Running the Project

## 1. Clone the repository

```bash
git clone https://github.com/sameeryellamandala/Agentic-AI-travel-planner.git
cd Agentic-AI-travel-planner
```

## 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it.

### Windows

```bash
.venv\Scripts\activate
```

### Linux/macOS

```bash
source .venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure environment variables

Create:

```text
.env
```

and provide the required API keys.

## 5. Run the application

Use the project's configured FastAPI or Streamlit entry point.

For FastAPI, for example:

```bash
uvicorn app.main:app --reload
```

For Streamlit, for example:

```bash
streamlit run app.py
```

Use the actual entry point present in the repository.

---

# 🧪 Testing

The project should include tests for:

### Request validation

```text
Valid request → valid TripPlan
Invalid request → validation error
```

### Tool calling

```text
LLM
 ↓
Tool call
 ↓
Tool execution
 ↓
ToolMessage
 ↓
LLM
```

### Multiple tools

Verify that the LLM can request multiple tools when required.

### Day isolation

Verify:

```text
Day 1 weather ≠ Day 2 weather
```

and that observations do not leak between days.

### Date propagation

Verify exact dates:

```text
Day 1 → 2026-10-10
Day 2 → 2026-10-11
Day 3 → 2026-10-12
```

### Train fare calculation

Verify:

```text
distance × class rate
```

for:

```text
SL
3A
2A
1A
```

### Random reproducibility

Same:

```text
seed + candidate set
```

should produce the same selection.

### Provider failures

Verify that API failures:

```text
do not create fake data
do not return fake ₹0 prices
do not restart the trip
```

### Transport legs

Verify transport is calculated only for:

```text
source → destination
```

and not for local sightseeing.

### End-to-end

Run a complete multi-day trip request and verify a valid `TripPlan`.

---

# 🧠 Example

A user submits:

```text
Plan a 4-day trip from Bangalore to Goa
for 2 people.

Dates:
10 October 2026 → 13 October 2026

Interests:
beaches
temples
seafood
sightseeing

Transport:
Train

Budget:
₹30,000
```

The system processes the request:

```text
User Request
     ↓
Validate
     ↓
Create Trip Blueprint
     ↓
Train:
Bangalore → Goa
     ↓
Determine railway distance
     ↓
Calculate:
SL / 3A / 2A / 1A
     ↓
Search Stay
     ↓
Initialize Day 1
     ↓
LLM decides required tools
     ↓
Weather + Wikipedia
     ↓
ToolMessages
     ↓
LLM creates Day 1
     ↓
Initialize Day 2
     ↓
Weather + Wikipedia if required
     ↓
LLM creates Day 2
     ↓
Initialize Day 3
     ↓
LLM creates Day 3
     ↓
Initialize Day 4
     ↓
LLM creates Day 4
     ↓
Goa → Bangalore transport leg
     ↓
Calculate final budget
     ↓
Finalize TripPlan
```

The final response contains:

```text
Trip Summary

Transport
Bangalore → Goa
Goa → Bangalore

Train fares
Sleeper
3A
2A
1A

Accommodation
Stay information

Day 1
Date
Weather
Places
Food
Activities

Day 2
Date
Weather
Places
Food
Activities

Day 3
...

Day 4
...

Budget
Warnings
Randomization information
```

---

# 🎯 Design Principles

The project follows these principles:

### 1. LLM decides, tools provide facts

The LLM decides what information it needs.

Tools retrieve or calculate the information.

---

### 2. Never fabricate real-world data

The system must not invent:

```text
Weather
Flights
Train distance
Train prices
Hotel prices
Availability
Opening hours
Places
Food facts
```

---

### 3. Deterministic calculations

Financial calculations and other deterministic calculations are performed in Python rather than relying on LLM arithmetic.

---

### 4. Randomness is controlled

Randomness only selects from genuine candidates returned by tools.

---

### 5. Day context is isolated

Every day has its own date, location, observations, and plan.

---

### 6. Provider failures are explicit

Unavailable information is represented as `UNAVAILABLE` and surfaced as a warning.

---

### 7. No unnecessary replanning

The planner continues with available information rather than restarting the entire trip.

---

# 📌 Current Scope

The current system focuses on:

* Agentic trip planning
* Flights
* Train fare estimation
* Accommodation
* Weather
* Famous places
* Historical/cultural attractions
* Famous/local food
* Day-by-day itinerary generation
* Budget calculation
* Controlled random selection

Local transportation pricing, bus transportation, and dynamic whole-trip replanning are **outside the current scope**.

---
# 👨‍💻 Author

**Sameer Yellamandala**

GitHub:

https://github.com/sameeryellamandala

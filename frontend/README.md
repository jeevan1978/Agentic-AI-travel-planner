# VoyageAI React interface

Optional React/Vite UI for the existing backend. Streamlit is launched separately from the root.

## Run

Start `python api.py` from the root. In this directory:

```powershell
npm ci
npm run dev
```

Open the URL Vite prints, normally http://localhost:5173. The client posts to http://localhost:8080/api/plan. The backend permits the default localhost Vite origin.

## Verify

```powershell
npm run build
npm run lint
npm run preview
```

Preview is for inspecting the build; API submission from its different port may require a backend CORS update.

## Behavior and files

Train selection reveals required one-way railway distance and budget class inputs. Results show four estimates. Flight uses Ignav. Missing data, partial plans and warnings are displayed explicitly.

`src/App.jsx` handles forms/results; `src/index.css` provides styling. Keys stay in the backend `.env`, never in this client. `node_modules/` and `dist/` are ignored.

See the root [README](../README.md), [UML diagrams](../docs/architecture.md) and [API contract](../docs/api.md).

# Cleanup record

Files below were removed after checking imports and asset references. The application remains in the existing project.

| Removed files | Reason |
| --- | --- |
| PRD_UPDATE.md, PRD_LLM_DRIVEN.md | Superseded guides describing replanning; replaced with current architecture/API documentation |
| schemas/tools.py | Unused obsolete schemas, including local-transit contracts |
| services/mock_apis.py | Unused retired mock stubs |
| services/pexels_service.py | Unused photo integration |
| services/places_service.py, services/food_service.py | Unused aliases; graph imports Wikipedia directly |
| frontend/src/App.css | Unimported starter styles |
| frontend/src/assets/vite.svg, react.svg, hero.png | Unreferenced assets |
| frontend/public/icons.svg | Unreferenced starter icon sheet |

The active favicon, tests, provider adapters, .env, package lockfile and example runner are retained. The original Word requirements document is moved to docs/reference with a superseded-requirements notice.

Generated output/*.json diagnostics are ignored by Git and preserved locally for inspection. Installed dependencies and build output remain ignored local artifacts. Snapshots are never production fallback data.

Verification after cleanup: default pytest suite, frontend build and lint. No live model call is needed to verify documentation or unused file removal.

import os
import requests
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
DEFAULT_HEADERS = {
    "User-Agent": os.getenv("WIKIPEDIA_USER_AGENT", "TravelPlanner/2.0")
}

def _fetch_wikipedia_extracts(titles: List[str], timeout: int = 8) -> Dict[str, Dict[str, str]]:
    """
    Given a list of Wikipedia page titles, queries MediaWiki API for canonical URLs and plain-text extracts.
    """
    if not titles:
        return {}

    params = {
        "action": "query",
        "prop": "extracts|info",
        "inprop": "url",
        "exintro": 1,
        "explaintext": 1,
        "exsentences": 3,
        "titles": "|".join(titles),
        "format": "json",
        "utf8": 1
    }

    try:
        response = requests.get(WIKIPEDIA_API_URL, params=params, headers=DEFAULT_HEADERS, timeout=timeout)
        if response.status_code != 200:
            logger.warning(f"Wikipedia extracts returned HTTP {response.status_code}")
            return {}

        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        results = {}
        for page_id, page_info in pages.items():
            if page_id == "-1":
                continue
            title = page_info.get("title", "")
            extract = page_info.get("extract", "").strip()
            url = page_info.get("fullurl", f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}")
            if title:
                # Clean multiple newlines and keep extract concise
                clean_extract = " ".join(extract.split())
                results[title.lower()] = {
                    "title": title,
                    "extract": clean_extract[:400] + ("..." if len(clean_extract) > 400 else "") if clean_extract else "",
                    "url": url,
                    "source": "Wikipedia"
                }
        return results
    except Exception as exc:
        logger.error(f"Error fetching Wikipedia page extracts: {exc}")
        return {}


def search_wikipedia_places(
    location: str,
    query: Optional[str] = None,
    interests: Optional[List[str]] = None,
    limit: int = 4
) -> Dict[str, Any]:
    """
    Searches Wikipedia/MediaWiki for factual notable places and attractions in a destination.
    Returns factual page title, concise extract, and canonical URL.
    Does NOT fabricate opening hours or prices.
    """
    clean_loc = location.strip()
    if not clean_loc:
        return {
            "status": "UNAVAILABLE",
            "source": "Wikipedia",
            "source_type": "UNAVAILABLE",
            "location": location,
            "places": [],
            "reason": "No location provided for places search"
        }

    # Build search query
    subquery = query.strip() if query else ""
    if not subquery and interests:
        subquery = " ".join(interests[:2])
    
    search_term = subquery if clean_loc.lower() in subquery.lower() else f"{clean_loc} {subquery}".strip()
    if not subquery:
        search_term = f"Tourist attractions in {clean_loc}"

    params = {
        "action": "query",
        "list": "search",
        "srsearch": search_term,
        "srlimit": max(limit, 4),
        "format": "json",
        "utf8": 1
    }

    try:
        response = requests.get(WIKIPEDIA_API_URL, params=params, headers=DEFAULT_HEADERS, timeout=8)
        if response.status_code != 200:
            return {
                "status": "UNAVAILABLE",
                "source": "Wikipedia",
                "source_type": "UNAVAILABLE",
                "location": location,
                "places": [],
                "reason": f"MediaWiki returned HTTP {response.status_code}"
            }

        data = response.json()
        search_items = data.get("query", {}).get("search", [])
        if not search_items:
            # Fallback search directly by location name
            params["srsearch"] = f"{clean_loc} tourism landmarks"
            resp2 = requests.get(WIKIPEDIA_API_URL, params=params, headers=DEFAULT_HEADERS, timeout=8)
            if resp2.status_code == 200:
                search_items = resp2.json().get("query", {}).get("search", [])

        if not search_items:
            return {
                "status": "UNAVAILABLE",
                "source": "Wikipedia",
                "source_type": "UNAVAILABLE",
                "location": location,
                "places": [],
                "reason": f"No Wikipedia entries found for '{location}'"
            }

        titles = [item["title"] for item in search_items[:limit]]
        extracts_map = _fetch_wikipedia_extracts(titles)

        places = []
        for item in search_items:
            t = item["title"]
            info = extracts_map.get(t.lower())
            if info and info.get("extract"):
                places.append({
                    "name": info["title"],
                    "description": info["extract"],
                    "url": info["url"],
                    "source": "Wikipedia",
                    "category": "Landmark / Attraction",
                    "estimated_cost": None # No fabricated entry fees
                })
            else:
                snippet = item.get("snippet", "").replace('<span class="searchmatch">', '').replace('</span>', '')
                places.append({
                    "name": t,
                    "description": snippet,
                    "url": f"https://en.wikipedia.org/wiki/{t.replace(' ', '_')}",
                    "source": "Wikipedia",
                    "category": "Landmark / Attraction",
                    "estimated_cost": None
                })
            if len(places) >= limit:
                break

        return {
            "status": "SUCCESS",
            "source": "Wikipedia",
            "source_type": "LIVE",
            "location": location,
            "places": places
        }

    except Exception as exc:
        logger.error(f"Wikipedia search error for places in {location}: {exc}")
        return {
            "status": "UNAVAILABLE",
            "source": "Wikipedia",
            "source_type": "UNAVAILABLE",
            "location": location,
            "places": [],
            "reason": str(exc)
        }


def search_wikipedia_food(
    location: str,
    query: Optional[str] = None,
    preferences: Optional[List[str]] = None,
    limit: int = 4
) -> Dict[str, Any]:
    """
    Searches Wikipedia/MediaWiki for factual local cuisine and dishes in a destination.
    Returns dish/cuisine name, factual extract, and canonical URL.
    Does NOT fabricate restaurant availability or prices.
    """
    clean_loc = location.strip()
    if not clean_loc:
        return {
            "status": "UNAVAILABLE",
            "source": "Wikipedia",
            "source_type": "UNAVAILABLE",
            "location": location,
            "food_items": [],
            "reason": "No location provided for food search"
        }

    subquery = query.strip() if query else ""
    if not subquery and preferences:
        subquery = " ".join(preferences[:2])

    search_term = (subquery if clean_loc.lower() in subquery.lower() else f"{clean_loc} {subquery}") if subquery else f"Cuisine of {clean_loc}"

    params = {
        "action": "query",
        "list": "search",
        "srsearch": search_term,
        "srlimit": max(limit, 4),
        "format": "json",
        "utf8": 1
    }

    try:
        response = requests.get(WIKIPEDIA_API_URL, params=params, headers=DEFAULT_HEADERS, timeout=8)
        if response.status_code != 200:
            return {
                "status": "UNAVAILABLE",
                "source": "Wikipedia",
                "source_type": "UNAVAILABLE",
                "location": location,
                "food_items": [],
                "reason": f"MediaWiki returned HTTP {response.status_code}"
            }

        data = response.json()
        search_items = data.get("query", {}).get("search", [])
        if not search_items:
            params["srsearch"] = f"{clean_loc} traditional dishes food"
            resp2 = requests.get(WIKIPEDIA_API_URL, params=params, headers=DEFAULT_HEADERS, timeout=8)
            if resp2.status_code == 200:
                search_items = resp2.json().get("query", {}).get("search", [])

        if not search_items:
            return {
                "status": "UNAVAILABLE",
                "source": "Wikipedia",
                "source_type": "UNAVAILABLE",
                "location": location,
                "food_items": [],
                "reason": f"No culinary Wikipedia entries found for '{location}'"
            }

        titles = [item["title"] for item in search_items[:limit]]
        extracts_map = _fetch_wikipedia_extracts(titles)

        food_items = []
        for item in search_items:
            t = item["title"]
            info = extracts_map.get(t.lower())
            if info and info.get("extract"):
                food_items.append({
                    "name": info["title"],
                    "description": info["extract"],
                    "url": info["url"],
                    "source": "Wikipedia",
                    "category": "Local Cuisine",
                    "estimated_cost": None # No fabricated meal prices
                })
            else:
                snippet = item.get("snippet", "").replace('<span class="searchmatch">', '').replace('</span>', '')
                food_items.append({
                    "name": t,
                    "description": snippet,
                    "url": f"https://en.wikipedia.org/wiki/{t.replace(' ', '_')}",
                    "source": "Wikipedia",
                    "category": "Local Cuisine",
                    "estimated_cost": None
                })
            if len(food_items) >= limit:
                break

        return {
            "status": "SUCCESS",
            "source": "Wikipedia",
            "source_type": "LIVE",
            "location": location,
            "food_items": food_items
        }

    except Exception as exc:
        logger.error(f"Wikipedia search error for food in {location}: {exc}")
        return {
            "status": "UNAVAILABLE",
            "source": "Wikipedia",
            "source_type": "UNAVAILABLE",
            "location": location,
            "food_items": [],
            "reason": str(exc)
        }

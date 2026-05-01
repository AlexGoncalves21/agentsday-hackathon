from __future__ import annotations

from typing import Dict, Iterable, List

from .models import InputDocument

CATEGORIES = ["topics", "concepts", "people", "companies", "projects", "events", "works", "sources"]

CATEGORY_BY_SLUG = {
    "demis-hassabis": "people",
    "multiverse-computing": "companies",
    "batalha-de-aljubarrota": "events",
    "all-tomorrows": "works",
    "agent-frameworks-and-elixir-otp": "topics",
}

RELATED_BY_SLUG = {
    "intelligence-vs-agency": [
        "agent-frameworks-and-elixir-otp",
        "decision-theory",
        "design-patterns",
    ],
    "agent-frameworks-and-elixir-otp": [
        "intelligence-vs-agency",
        "design-patterns",
        "lei-de-murphy",
        "self-hosting",
    ],
    "demis-hassabis": [
        "game-theory",
        "decision-theory",
    ],
    "game-theory": [
        "decision-theory",
        "batalha-de-aljubarrota",
        "tatica-do-quadrado",
    ],
    "decision-theory": [
        "game-theory",
        "monte-carlo-and-markov-chains",
        "intelligence-vs-agency",
    ],
    "design-patterns": [
        "agent-frameworks-and-elixir-otp",
        "tatica-do-quadrado",
        "intelligence-vs-agency",
    ],
    "lei-de-murphy": [
        "agent-frameworks-and-elixir-otp",
        "self-hosting",
    ],
    "fibonacci": [
        "conways-game-of-life",
        "monte-carlo-and-markov-chains",
    ],
    "batalha-de-aljubarrota": [
        "game-theory",
        "decision-theory",
        "tatica-do-quadrado",
    ],
    "self-hosting": [
        "multiverse-computing",
        "agent-frameworks-and-elixir-otp",
        "lei-de-murphy",
    ],
    "monte-carlo-and-markov-chains": [
        "decision-theory",
        "conways-game-of-life",
        "fibonacci",
    ],
    "conways-game-of-life": [
        "fibonacci",
        "monte-carlo-and-markov-chains",
        "all-tomorrows",
    ],
    "tatica-do-quadrado": [
        "game-theory",
        "batalha-de-aljubarrota",
        "design-patterns",
    ],
    "multiverse-computing": [
        "self-hosting",
        "intelligence-vs-agency",
    ],
    "all-tomorrows": [
        "conways-game-of-life",
    ],
}


def category_for(document: InputDocument) -> str:
    return CATEGORY_BY_SLUG.get(document.slug, "concepts")


def related_slugs_for(document: InputDocument, all_documents: Iterable[InputDocument]) -> List[str]:
    available = {doc.slug for doc in all_documents}
    explicit = [slug for slug in RELATED_BY_SLUG.get(document.slug, []) if slug in available]
    heuristic = [
        other.slug
        for other in all_documents
        if other.slug != document.slug and _shares_interesting_word(document.title, other.title)
    ]
    return list(dict.fromkeys(explicit + heuristic))


def _shares_interesting_word(left: str, right: str) -> bool:
    stopwords = {"and", "the", "of", "de", "do", "da", "e"}
    left_words = {word for word in left.lower().replace("/", " ").split() if word not in stopwords}
    right_words = {word for word in right.lower().replace("/", " ").split() if word not in stopwords}
    return bool(left_words & right_words)


def group_by_category(documents: Iterable[InputDocument]) -> Dict[str, List[InputDocument]]:
    grouped: Dict[str, List[InputDocument]] = {category: [] for category in CATEGORIES if category != "sources"}
    for document in sorted(documents, key=lambda item: item.title.lower()):
        grouped.setdefault(category_for(document), []).append(document)
    return grouped


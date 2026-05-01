from __future__ import annotations

import math
import re
from collections import Counter
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

TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)
MAX_RELEVANT_TERMS = 14
MAX_RELATED_SLUGS = 6
MIN_SHARED_TFIDF_SCORE = 0.28


def category_for(document: InputDocument) -> str:
    return CATEGORY_BY_SLUG.get(document.slug, "concepts")


def related_slugs_for(document: InputDocument, all_documents: Iterable[InputDocument]) -> List[str]:
    documents = list(all_documents)
    relevant_terms_by_slug = _relevant_terms_by_slug(documents)
    document_terms = relevant_terms_by_slug.get(document.slug, {})
    related = []
    for other in documents:
        if other.slug == document.slug:
            continue
        shared_terms = document_terms.keys() & relevant_terms_by_slug.get(other.slug, {}).keys()
        shared_score = sum(min(document_terms[term], relevant_terms_by_slug[other.slug][term]) for term in shared_terms)
        if shared_score >= MIN_SHARED_TFIDF_SCORE:
            related.append((other.slug, shared_score, sorted(shared_terms)))
    related.sort(key=lambda item: (-item[1], item[0]))
    return [slug for slug, _score, _terms in related[:MAX_RELATED_SLUGS]]


def _relevant_terms_by_slug(documents: List[InputDocument]) -> Dict[str, Dict[str, float]]:
    term_counts_by_slug = {document.slug: _term_counts(document) for document in documents}
    document_frequency: Counter[str] = Counter()
    for term_counts in term_counts_by_slug.values():
        document_frequency.update(term_counts.keys())

    document_count = max(len(documents), 1)
    relevant_terms_by_slug = {}
    for document in documents:
        term_counts = term_counts_by_slug[document.slug]
        scores = {}
        for term, count in term_counts.items():
            idf = math.log((1 + document_count) / (1 + document_frequency[term])) + 1
            scores[term] = (1 + math.log(count)) * idf
        top_terms = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:MAX_RELEVANT_TERMS]
        relevant_terms_by_slug[document.slug] = {term: round(score, 4) for term, score in top_terms}
    return relevant_terms_by_slug


def _term_counts(document: InputDocument) -> Counter[str]:
    weighted_text = " ".join([document.title, document.slug, document.title, document.slug, document.information])
    return Counter(_tokens(weighted_text))


def _tokens(value: str) -> List[str]:
    stopwords = {
        "and",
        "the",
        "of",
        "de",
        "do",
        "da",
        "e",
        "is",
        "no",
        "a",
        "an",
        "to",
        "in",
        "for",
        "by",
        "with",
        "from",
        "and",
        "or",
        "not",
        "post",
        "source",
        "information",
        "topic",
        "concept",
        "input",
        "file",
        "original",
        "summary",
        "compiled",
        "into",
        "http",
        "https",
        "www",
        "com",
        "example",
    }
    short_terms = {"ai", "ui", "llm"}
    tokens = []
    for raw_token in TOKEN_RE.findall(value.lower().replace("/", " ").replace("-", " ")):
        token = _normalize_token(raw_token)
        if token in stopwords:
            continue
        if len(token) <= 2 and token not in short_terms:
            continue
        tokens.append(token)
    return tokens


def _normalize_token(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("s"):
        return token[:-1]
    return token


def group_by_category(documents: Iterable[InputDocument]) -> Dict[str, List[InputDocument]]:
    grouped: Dict[str, List[InputDocument]] = {category: [] for category in CATEGORIES if category != "sources"}
    for document in sorted(documents, key=lambda item: item.title.lower()):
        grouped.setdefault(category_for(document), []).append(document)
    return grouped

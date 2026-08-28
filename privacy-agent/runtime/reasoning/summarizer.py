from __future__ import annotations

import re


def summarize_article(text: str, max_sentences: int = 5) -> str:
    """Create a compact, deterministic summary from sanitized page text."""
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return "No readable article text was found on the current page."

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", cleaned)
        if len(sentence.strip()) >= 40
    ]
    if not sentences:
        return cleaned[:900]

    scored = sorted(
        enumerate(sentences[:40]),
        key=lambda item: (_score_sentence(item[1]), -item[0]),
        reverse=True,
    )
    selected_indexes = sorted(index for index, _sentence in scored[:max_sentences])
    return " ".join(sentences[index] for index in selected_indexes)


def _score_sentence(sentence: str) -> int:
    words = re.findall(r"[A-Za-z][A-Za-z'-]{3,}", sentence.lower())
    if not words:
        return 0
    signal_terms = {
        "because",
        "change",
        "could",
        "data",
        "found",
        "important",
        "increase",
        "new",
        "people",
        "reported",
        "research",
        "result",
        "said",
        "study",
        "system",
        "technology",
        "today",
        "work",
    }
    unique_words = len(set(words))
    signal_hits = sum(1 for word in words if word in signal_terms)
    length_bonus = min(len(words), 35)
    return unique_words + signal_hits * 3 + length_bonus

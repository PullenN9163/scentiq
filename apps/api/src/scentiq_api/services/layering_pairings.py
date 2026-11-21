"""Researched layering knowledge: reported fragrance pairs and signal-family pairing rules.

Scores are 0-1 starting priors, not measurements. Provenance is explicit:

* ``reported``: a named pair a community member reported liking (single anecdote, low prior).
* ``editorial``: a pairing recommended by a published layering guide.
* ``heuristic``: a conventional perfumery pairing rule (shared bridge, classic contrast).

User wear ratings for the same set later pull the prior toward observed taste
(see ``shrink_prior``). Nothing here is a chemistry or safety claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Confidence = Literal["reported", "editorial", "heuristic"]

# Weight of the prior, expressed as an equivalent number of user ratings.
PRIOR_STRENGTH = {"reported": 2.0, "editorial": 3.0, "heuristic": 4.0}


@dataclass(frozen=True)
class KnownPair:
    """A specific reported pair, matched on lower-cased brand+name substrings."""

    first: str
    second: str
    score: float
    confidence: Confidence
    source: str
    note: str


@dataclass(frozen=True)
class SignalRule:
    """A pairing between two groups of notes/accords/families."""

    first: frozenset[str]
    second: frozenset[str]
    score: float
    confidence: Confidence
    source: str
    label: str


FORUM = "https://basenotes.com/threads/layering-frags.302676/"
SEPHORA = "https://community.sephora.com/t5/Fragrance-Fans/Olfactory-Overtures-The-Fragrance-Layering-Thread/m-p/7237410/highlight/true"
COVETEUR = "https://coveteur.com/best-perfume-layering-combinations"
BEAUTYBAY = "https://beautybay.com/edited/how-to-layer-fragrances"

KNOWN_PAIRS: tuple[KnownPair, ...] = (
    KnownPair(
        "black suede",
        "amber pour homme",
        0.82,
        "reported",
        FORUM,
        "Reported as a best result: suede/leather under a resinous amber.",
    ),
    KnownPair(
        "millesime imperial",
        "virgin island water",
        0.78,
        "reported",
        FORUM,
        "Reported at roughly 4:1; a fresh marine lift on a fruity-fresh base.",
    ),
    KnownPair(
        "nahema",
        "m7",
        0.7,
        "reported",
        FORUM,
        "Reported in equal proportions; rose-lush floral over a resinous oud-woody base.",
    ),
    KnownPair(
        "fleur de peau",
        "poets of berlin",
        0.72,
        "reported",
        SEPHORA,
        "Reported on Sephora community: musky-powdery skin scent plus a dry tobacco-woody.",
    ),
    KnownPair(
        "tonka",
        "matcha milk",
        0.62,
        "reported",
        SEPHORA,
        "Reported: a creamy matcha mist softens a tonka base.",
    ),
)

SIGNAL_RULES: tuple[SignalRule, ...] = (
    SignalRule(
        frozenset({"vetiver"}),
        frozenset({"cedar", "cedarwood"}),
        0.84,
        "editorial",
        COVETEUR,
        "Vetiver + cedar: dry woods that deepen each other.",
    ),
    SignalRule(
        frozenset({"cola", "cola-nut"}),
        frozenset({"coconut"}),
        0.7,
        "editorial",
        COVETEUR,
        "Cola + coconut: a fizzy, sweet tropical pairing.",
    ),
    SignalRule(
        frozenset({"citrus", "bergamot", "lemon", "grapefruit"}),
        frozenset({"woody", "cedar", "sandalwood", "vetiver"}),
        0.8,
        "editorial",
        BEAUTYBAY,
        "Citrus over woods: brightness lifting a dry base.",
    ),
    SignalRule(
        frozenset({"vanilla", "tonka", "tonka-bean"}),
        frozenset({"amber", "resin", "benzoin", "labdanum"}),
        0.82,
        "heuristic",
        BEAUTYBAY,
        "Vanilla + amber: a shared warm-sweet bridge.",
    ),
    SignalRule(
        frozenset({"tobacco"}),
        frozenset({"vanilla", "tonka", "tonka-bean", "honey"}),
        0.83,
        "heuristic",
        FORUM,
        "Tobacco + vanilla: a classic gourmand-leather bridge.",
    ),
    SignalRule(
        frozenset({"rose"}),
        frozenset({"oud", "patchouli", "incense"}),
        0.8,
        "heuristic",
        BEAUTYBAY,
        "Rose + oud/patchouli: floral against a dark resinous base.",
    ),
    SignalRule(
        frozenset({"leather", "suede"}),
        frozenset({"amber", "resin", "incense"}),
        0.78,
        "heuristic",
        FORUM,
        "Leather + amber/resin: smoky warmth.",
    ),
    SignalRule(
        frozenset({"aquatic", "marine", "fresh"}),
        frozenset({"aromatic", "lavender", "herbal", "green"}),
        0.74,
        "heuristic",
        BEAUTYBAY,
        "Fresh aquatic + aromatic herbs: a clean daytime pairing.",
    ),
    SignalRule(
        frozenset({"musk", "musky", "white-musk"}),
        frozenset({"floral", "white-floral", "jasmine", "iris"}),
        0.72,
        "heuristic",
        BEAUTYBAY,
        "Musk under florals: softens and extends them.",
    ),
    SignalRule(
        frozenset({"fruity", "apple", "pineapple", "berry"}),
        frozenset({"vanilla", "sweet", "caramel"}),
        0.66,
        "heuristic",
        BEAUTYBAY,
        "Fruit + sweet base: a dessert-like pairing.",
    ),
    SignalRule(
        frozenset({"citrus"}),
        frozenset({"vanilla", "gourmand", "caramel"}),
        0.38,
        "heuristic",
        BEAUTYBAY,
        "Sharp citrus and heavy gourmand tend to clash.",
    ),
    SignalRule(
        frozenset({"oud"}),
        frozenset({"aquatic", "marine", "ozonic"}),
        0.35,
        "heuristic",
        BEAUTYBAY,
        "Dense oud and ozonic marine tend to compete.",
    ),
)


def _label(fragrance_label: str) -> str:
    return fragrance_label.lower()


def known_pair_prior(first_label: str, second_label: str) -> KnownPair | None:
    """Match a specific reported pair from 'brand name' labels, order-insensitive."""
    a, b = _label(first_label), _label(second_label)
    for pair in KNOWN_PAIRS:
        if (pair.first in a and pair.second in b) or (pair.first in b and pair.second in a):
            return pair
    return None


def rule_prior(
    first: dict[str, float], second: dict[str, float]
) -> tuple[float, SignalRule | None]:
    """Strongest matching signal-family rule for two signal profiles.

    Returns (score, rule). When nothing matches the score is neutral (0.5, None).
    Matches are weighted by how strongly the signals are present so a faint
    accord cannot trigger a rule on its own.
    """
    best_score = 0.5
    best_rule: SignalRule | None = None
    best_strength = 0.0
    for rule in SIGNAL_RULES:
        for left, right in ((first, second), (second, first)):
            a = max((left.get(key, 0.0) for key in rule.first), default=0.0)
            b = max((right.get(key, 0.0) for key in rule.second), default=0.0)
            strength = min(a, b)
            if strength < 0.25:
                continue
            # Negative rules (<0.5) matter as much as positive ones; pick the strongest evidence.
            if strength > best_strength:
                best_strength = strength
                best_rule = rule
                best_score = 0.5 + (rule.score - 0.5) * min(1.0, strength + 0.3)
    return best_score, best_rule


def known_pairing_score(
    labels: list[str], profiles: list[dict[str, float]]
) -> tuple[float, list[str], Confidence | None]:
    """Mean pairing prior across every pair in a stack, with human-readable evidence.

    Specific reported pairs take precedence over signal rules for that pair.
    """
    scores: list[float] = []
    evidence: list[str] = []
    confidences: list[Confidence] = []
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            pair = known_pair_prior(labels[i], labels[j])
            if pair:
                scores.append(pair.score)
                evidence.append(f"Reported pairing: {pair.note}")
                confidences.append(pair.confidence)
                continue
            score, rule = rule_prior(profiles[i], profiles[j])
            if rule:
                scores.append(score)
                evidence.append(rule.label)
                confidences.append(rule.confidence)
    if not scores:
        return 0.5, [], None
    # Weakest pair limits a stack; blend with the mean so one great pair cannot hide a clash.
    value = 0.5 * min(scores) + 0.5 * (sum(scores) / len(scores))
    order: tuple[Confidence, ...] = ("heuristic", "editorial", "reported")
    return value, list(dict.fromkeys(evidence)), max(confidences, key=order.index)


def shrink_prior(prior: float, confidence: Confidence | None, ratings: list[int]) -> float:
    """Bayesian average of the prior and a user's own 1-5 ratings of this exact set."""
    if not ratings:
        return prior
    strength = PRIOR_STRENGTH.get(confidence or "heuristic", 4.0)
    observed = (sum(ratings) / len(ratings) - 1) / 4
    return (strength * prior + len(ratings) * observed) / (strength + len(ratings))

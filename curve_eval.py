"""
Curve evaluation module for mana curve analysis.
Scores deck curves and provides actionable warnings.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Set
import statistics


class CurveLevel(Enum):
    """Curve classification levels"""
    LOW = "low"  # Fast, low-to-the-ground
    BALANCED = "balanced"  # Well-distributed
    TOP_HEAVY = "top-heavy"  # High-cost concentration
    SPIKY = "spiky"  # Gaps and awkward distribution
    SLOW = "slow"  # Generally high curve with issues


@dataclass(frozen=True)
class Card:
    """
    Simplified card model for curve analysis.
    In practice, this would come from your parsed deck + Scryfall data.
    """
    name: str
    cmc: float
    type_line: str
    oracle_text: str
    colors: Set[str]
    mana_cost: str
    qty: int = 1
    
    @property
    def is_land(self) -> bool:
        return "Land" in self.type_line
    
    @property
    def is_creature(self) -> bool:
        return "Creature" in self.type_line
    
    @property
    def is_artifact(self) -> bool:
        return "Artifact" in self.type_line
    
    @property
    def is_x_spell(self) -> bool:
        return "X" in self.mana_cost if self.mana_cost else False


@dataclass(frozen=True)
class CurveEvalResult:
    """Complete curve analysis result"""
    curve_score: int  # 0-100
    curve_level: CurveLevel
    
    # Basic stats
    avg_mv: float
    median_mv: float
    mv_hist: Dict[int, int]  # MV -> count (includes quantities)
    
    # Density metrics
    early_density: float  # % nonlands at MV <= 2
    mid_density: float  # % nonlands at MV 3-4
    top_end_density: float  # % nonlands at MV >= 5
    
    # Mana support
    land_count: int
    ramp_count: int
    effective_mana_sources: float
    
    # Playability by turn
    playable_by_turn: Dict[int, int]  # turn -> # playable cards
    
    # Analysis
    warnings: List[str]
    notes: List[str]
    
    # Breakdown for transparency
    score_breakdown: Dict[str, int]
    
    @property
    def level(self) -> str:
        """Return curve level as string for UI display."""
        return self.curve_level.value.title()
    
    @property
    def mv_distribution(self) -> Dict[int, int]:
        """Alias for mv_hist for UI compatibility."""
        return self.mv_hist


@dataclass
class EvalContext:
    """Context for curve evaluation"""
    commander_cmc: Optional[float] = None
    commander_centric_count: int = 0  # Cards that need commander
    format: str = "commander"  # commander, modern, etc.


# ===== Ramp Detection =====

# Patterns that indicate ramp
RAMP_PATTERNS = {
    "add {",  # Mana rocks and dorks
    "adds {",
    "add one mana",
    "search your library for a basic land",
    "search your library for a land",
    "search your library for up to two basic land",
    "search your library for a plains, island, swamp, or mountain",
    "search your library for a forest",
    "put a land card from your hand onto the battlefield",
    "you may put a land",
}

RITUAL_PATTERNS = {
    "add {r}{r}{r}",
    "add {b}{b}{b}",
    "add {g}{g}{g}",
    "add {w}{w}{w}",
    "add {u}{u}{u}",
    "adds three mana",
    "ritual",
}

COST_REDUCER_PATTERNS = {
    "spells you cast cost",
    "costs {x} less to cast",
    "creature spells cost",
    "artifact spells cost",
}


def is_ramp_card(card: Card) -> tuple[bool, str]:
    """
    Detect if a card is ramp and classify its type.
    Returns (is_ramp, ramp_type)
    """
    if card.is_land:
        return False, ""
    
    text_lower = card.oracle_text.lower()
    
    # Check for rituals first (different weight)
    for pattern in RITUAL_PATTERNS:
        if pattern in text_lower:
            return True, "ritual"
    
    # Check for cost reducers
    for pattern in COST_REDUCER_PATTERNS:
        if pattern in text_lower:
            return True, "cost_reducer"
    
    # Check for standard ramp
    for pattern in RAMP_PATTERNS:
        if pattern in text_lower:
            # Distinguish mana rocks from land ramp
            if card.is_artifact and "add {" in text_lower:
                return True, "mana_rock"
            elif card.is_creature and "add {" in text_lower:
                return True, "mana_dork"
            elif "search" in text_lower or "land" in text_lower:
                return True, "land_ramp"
            else:
                return True, "other_ramp"
    
    return False, ""


def get_ramp_weight(card: Card, ramp_type: str) -> float:
    """
    Calculate effective mana source weight for ramp cards.
    """
    if card.cmc <= 2:
        if ramp_type == "mana_rock":
            return 0.7
        elif ramp_type == "mana_dork":
            return 0.6  # More vulnerable than rocks
        elif ramp_type == "land_ramp":
            return 0.6
        elif ramp_type == "ritual":
            return 0.2
        elif ramp_type == "cost_reducer":
            return 0.3
    elif card.cmc == 3:
        if ramp_type in ["mana_rock", "mana_dork"]:
            return 0.5
        elif ramp_type == "land_ramp":
            return 0.6
        elif ramp_type == "cost_reducer":
            return 0.4
    elif card.cmc >= 4:
        # Late ramp is less valuable for curve support
        if ramp_type == "land_ramp":
            return 0.4
        else:
            return 0.3
    
    return 0.3  # Default


# ===== Curve Analysis Functions =====

def split_lands_nonlands(cards: List[Card]) -> tuple[List[Card], List[Card]]:
    """Separate lands from nonlands"""
    lands = [c for c in cards if c.is_land]
    nonlands = [c for c in cards if not c.is_land]
    return lands, nonlands


def build_mv_histogram(cards: List[Card]) -> Dict[int, int]:
    """
    Build mana value histogram weighted by quantity.
    Special handling for X spells.
    """
    hist = {}
    
    for card in cards:
        if card.is_x_spell:
            # X spells typically cast for 4+ in Commander
            effective_mv = max(int(card.cmc), 4)
        else:
            effective_mv = int(card.cmc)
        
        # Cap at 7+ bucket
        bucket = min(effective_mv, 7)
        hist[bucket] = hist.get(bucket, 0) + card.qty
    
    return hist


def calculate_avg_mv(cards: List[Card]) -> float:
    """Calculate weighted average mana value"""
    if not cards:
        return 0.0
    
    total_mv = 0.0
    total_qty = 0
    
    for card in cards:
        mv = card.cmc
        if card.is_x_spell:
            mv = max(card.cmc, 4)
        total_mv += mv * card.qty
        total_qty += card.qty
    
    return total_mv / total_qty if total_qty > 0 else 0.0


def calculate_median_mv(cards: List[Card]) -> float:
    """Calculate weighted median mana value"""
    if not cards:
        return 0.0
    
    # Expand cards by quantity
    all_mvs = []
    for card in cards:
        mv = card.cmc
        if card.is_x_spell:
            mv = max(card.cmc, 4)
        all_mvs.extend([mv] * card.qty)
    
    return statistics.median(all_mvs) if all_mvs else 0.0


def calculate_density(cards: List[Card], min_mv: int = 0, max_mv: int = 99) -> float:
    """
    Calculate density of cards in a CMC range.
    Returns percentage (0.0 to 1.0).
    """
    if not cards:
        return 0.0
    
    in_range = sum(card.qty for card in cards if min_mv <= card.cmc <= max_mv)
    total = sum(card.qty for card in cards)
    
    return in_range / total if total > 0 else 0.0


def calculate_playable_by_turn(cards: List[Card]) -> Dict[int, int]:
    """
    Calculate how many cards are playable on each turn (assuming on-curve).
    """
    playable = {}
    for turn in range(1, 8):
        playable[turn] = sum(
            card.qty for card in cards 
            if card.cmc <= turn
        )
    return playable


def identify_ramp_cards(cards: List[Card]) -> List[tuple[Card, str]]:
    """Identify all ramp cards and their types"""
    ramp = []
    for card in cards:
        is_ramp, ramp_type = is_ramp_card(card)
        if is_ramp:
            ramp.append((card, ramp_type))
    return ramp


def calculate_effective_sources(
    lands: List[Card],
    ramp_cards: List[tuple[Card, str]]
) -> float:
    """
    Calculate effective mana sources with proper weighting.
    """
    # Lands count as 1.0 each
    land_value = sum(card.qty for card in lands)
    
    # Ramp is weighted by type and CMC
    ramp_value = sum(
        get_ramp_weight(card, ramp_type) * card.qty
        for card, ramp_type in ramp_cards
    )
    
    return land_value + ramp_value


# ===== Warning Generation =====

def generate_land_warnings(
    land_count: int,
    avg_mv: float,
    effective_sources: float
) -> List[str]:
    """Generate warnings about land count"""
    warnings = []
    
    # Expected sources based on curve
    expected_sources = 34 + (avg_mv - 3.0) * 3
    
    if land_count < 32:
        warnings.append(f"Very low land count ({land_count}) - mulligan rate will be high")
    elif land_count < 34:
        warnings.append(f"Low land count ({land_count}) for Commander format")
    
    if avg_mv > 3.3 and land_count < 37:
        warnings.append(
            f"High average MV ({avg_mv:.2f}) with only {land_count} lands - "
            "expect frequent mana issues"
        )
    
    if effective_sources < expected_sources * 0.85:
        warnings.append(
            f"Effective mana sources ({effective_sources:.1f}) are low for curve "
            f"(expected ~{expected_sources:.0f})"
        )
    
    return warnings


def generate_ramp_warnings(
    ramp_count: int,
    land_count: int,
    avg_mv: float
) -> List[str]:
    """Generate warnings about ramp density"""
    warnings = []
    
    # Expected ramp by curve
    if avg_mv <= 2.5:
        expected_ramp = 8
        tier = "nice to have"
    elif avg_mv <= 3.0:
        expected_ramp = 10
        tier = "standard"
    elif avg_mv <= 3.4:
        expected_ramp = 12
        tier = "needed"
    else:
        expected_ramp = 14
        tier = "critical"
    
    if ramp_count < expected_ramp:
        warnings.append(
            f"Low ramp count ({ramp_count}) for average MV {avg_mv:.2f} "
            f"- recommend {expected_ramp}+ ({tier})"
        )
    
    return warnings


def generate_density_warnings(
    early_density: float,
    mid_density: float,
    top_end_density: float
) -> List[str]:
    """Generate warnings about curve density distribution"""
    warnings = []
    
    # Early game
    if early_density < 0.15:
        warnings.append(
            f"Very low early game ({early_density:.1%} at MV ≤2) - "
            "deck may do nothing before turn 3-4"
        )
    elif early_density < 0.20:
        warnings.append(
            f"Low early game density ({early_density:.1%} at MV ≤2) - "
            "limited turn 1-2 plays"
        )
    
    # Top end
    if top_end_density > 0.40:
        warnings.append(
            f"Very top-heavy curve ({top_end_density:.1%} at MV ≥5) - "
            "expect frequent clunky hands"
        )
    elif top_end_density > 0.32:
        warnings.append(
            f"Top-heavy curve ({top_end_density:.1%} at MV ≥5) - "
            "may have slow starts"
        )
    
    # Middle game gap
    if mid_density < 0.20 and early_density < 0.25:
        warnings.append(
            "Low mid-game presence (MV 3-4) and weak early game - "
            "curve has awkward gaps"
        )
    
    return warnings


def generate_spikiness_warnings(mv_hist: Dict[int, int]) -> List[str]:
    """Detect and warn about spiky/gappy curves"""
    warnings = []
    
    if not mv_hist:
        return warnings
    
    total = sum(mv_hist.values())
    if total == 0:
        return warnings
    
    # Check for missing critical MV slots
    missing_slots = []
    for mv in range(2, 5):
        if mv_hist.get(mv, 0) == 0:
            missing_slots.append(mv)
    
    if missing_slots:
        warnings.append(
            f"Spiky curve: missing cards at MV {', '.join(map(str, missing_slots))} - "
            "likely dead turns in gameplay"
        )
    
    # Check for over-concentration in one slot
    for mv, count in mv_hist.items():
        concentration = count / total
        if concentration > 0.35:
            warnings.append(
                f"Over-concentrated at MV {mv} ({concentration:.1%}) - "
                "may create bottlenecks"
            )
            break  # Only warn once
    
    # Check for extreme gap between early and late
    early_total = sum(mv_hist.get(i, 0) for i in range(0, 3))
    late_total = sum(mv_hist.get(i, 0) for i in range(5, 8))
    
    if early_total < total * 0.15 and late_total > total * 0.40:
        warnings.append(
            "Extreme curve gap: very few early plays but many expensive spells - "
            "will struggle to stabilize"
        )
    
    return warnings


def generate_commander_warnings(
    ctx: EvalContext,
    avg_mv: float,
    ramp_count: int
) -> List[str]:
    """Generate warnings related to commander-centric builds"""
    warnings = []
    
    if ctx.commander_cmc and ctx.commander_centric_count > 15:
        # Deck is heavily reliant on commander
        if ctx.commander_cmc >= 5 and ramp_count < 12:
            warnings.append(
                f"Deck relies heavily on {ctx.commander_cmc} MV commander "
                f"but has only {ramp_count} ramp pieces - "
                "commander will be slow/vulnerable"
            )
    
    return warnings


# ===== Scoring =====

def score_mana_support(
    effective_sources: float,
    avg_mv: float,
    max_points: int = 40
) -> tuple[int, str]:
    """
    Score mana support (lands + ramp) adequacy.
    40 points available.
    """
    expected_sources = 34 + (avg_mv - 3.0) * 3
    ratio = effective_sources / expected_sources if expected_sources > 0 else 0
    
    if ratio >= 1.05:
        score = max_points
        note = "Excellent mana support"
    elif ratio >= 0.95:
        score = int(max_points * 0.95)
        note = "Strong mana support"
    elif ratio >= 0.85:
        score = int(max_points * 0.75)
        note = "Adequate mana support"
    elif ratio >= 0.75:
        score = int(max_points * 0.50)
        note = "Below-average mana support"
    else:
        score = int(max_points * ratio * 0.6)
        note = "Insufficient mana support"
    
    return score, note


def score_early_game(early_density: float, max_points: int = 25) -> tuple[int, str]:
    """
    Score early game presence.
    25 points available.
    """
    if early_density >= 0.28:
        score = max_points
        note = "Strong early game presence"
    elif early_density >= 0.22:
        score = int(max_points * 0.90)
        note = "Good early game"
    elif early_density >= 0.18:
        score = int(max_points * 0.75)
        note = "Adequate early game"
    elif early_density >= 0.12:
        score = int(max_points * 0.50)
        note = "Weak early game"
    else:
        score = int(max_points * early_density * 3)
        note = "Very weak early game"
    
    return score, note


def score_top_end(top_end_density: float, max_points: int = 20) -> tuple[int, str]:
    """
    Score top-end sanity (penalize too many expensive spells).
    20 points available.
    """
    if top_end_density <= 0.22:
        score = max_points
        note = "Well-balanced top end"
    elif top_end_density <= 0.28:
        score = int(max_points * 0.90)
        note = "Reasonable top end"
    elif top_end_density <= 0.35:
        score = int(max_points * 0.70)
        note = "Heavy top end"
    elif top_end_density <= 0.42:
        score = int(max_points * 0.40)
        note = "Very top-heavy"
    else:
        score = int(max_points * 0.20)
        note = "Extremely top-heavy"
    
    return score, note


def score_smoothness(mv_hist: Dict[int, int], max_points: int = 15) -> tuple[int, str]:
    """
    Score curve smoothness (penalize gaps and spikes).
    15 points available.
    """
    if not mv_hist:
        return 0, "No curve data"
    
    penalty = 0
    
    # Penalize missing MV slots
    for mv in range(2, 6):
        if mv_hist.get(mv, 0) == 0:
            penalty += 3
    
    # Penalize over-concentration
    total = sum(mv_hist.values())
    if total > 0:
        max_concentration = max(mv_hist.values()) / total
        if max_concentration > 0.35:
            penalty += 5
        elif max_concentration > 0.30:
            penalty += 3
    
    score = max(0, max_points - penalty)
    
    if penalty == 0:
        note = "Smooth, well-distributed curve"
    elif penalty <= 5:
        note = "Minor curve irregularities"
    else:
        note = "Spiky, uneven curve"
    
    return score, note


def calculate_total_score(
    mana_score: int,
    early_score: int,
    top_score: int,
    smooth_score: int
) -> int:
    """Calculate final 0-100 score"""
    total = mana_score + early_score + top_score + smooth_score
    return max(0, min(100, total))


# ===== Curve Level Classification =====

def determine_curve_level(
    avg_mv: float,
    early_density: float,
    top_end_density: float,
    warnings: List[str]
) -> CurveLevel:
    """Classify the overall curve level"""
    
    # Check for specific problems first
    spiky_warnings = [w for w in warnings if "spiky" in w.lower() or "gap" in w.lower()]
    if spiky_warnings:
        return CurveLevel.SPIKY
    
    # Low/fast curve
    if avg_mv < 2.5 and early_density >= 0.25:
        return CurveLevel.LOW
    
    # Top-heavy
    if avg_mv > 3.3 or top_end_density > 0.32:
        return CurveLevel.TOP_HEAVY
    
    # Balanced
    if 2.5 <= avg_mv <= 3.2 and early_density >= 0.18 and top_end_density <= 0.32:
        return CurveLevel.BALANCED
    
    # Slow (catch-all for problematic curves)
    return CurveLevel.SLOW


# ===== Main Evaluation Function =====

def evaluate_curve(
    cards: List[Card],
    context: Optional[EvalContext] = None
) -> CurveEvalResult:
    """
    Main curve evaluation function.
    
    Args:
        cards: List of Card objects (with quantities)
        context: Optional evaluation context
        
    Returns:
        Complete CurveEvalResult
    """
    if context is None:
        context = EvalContext()
    
    # 1. Separate lands and nonlands
    lands, nonlands = split_lands_nonlands(cards)
    
    if not nonlands:
        # Edge case: all lands
        return CurveEvalResult(
            curve_score=0,
            curve_level=CurveLevel.SLOW,
            avg_mv=0.0,
            median_mv=0.0,
            mv_hist={},
            early_density=0.0,
            mid_density=0.0,
            top_end_density=0.0,
            land_count=sum(c.qty for c in lands),
            ramp_count=0,
            effective_mana_sources=sum(c.qty for c in lands),
            playable_by_turn={},
            warnings=["Deck contains only lands"],
            notes=[],
            score_breakdown={}
        )
    
    # 2. Build MV histogram
    mv_hist = build_mv_histogram(nonlands)
    
    # 3. Calculate curve stats
    avg_mv = calculate_avg_mv(nonlands)
    median_mv = calculate_median_mv(nonlands)
    
    # 4. Calculate densities
    early_density = calculate_density(nonlands, min_mv=0, max_mv=2)
    mid_density = calculate_density(nonlands, min_mv=3, max_mv=4)
    top_end_density = calculate_density(nonlands, min_mv=5, max_mv=99)
    
    # 5. Identify ramp
    ramp_cards = identify_ramp_cards(nonlands)
    ramp_count = sum(card.qty for card, _ in ramp_cards)
    
    # 6. Calculate effective mana sources
    effective_sources = calculate_effective_sources(lands, ramp_cards)
    
    # 7. Playability by turn
    playable_by_turn = calculate_playable_by_turn(nonlands)
    
    # 8. Generate warnings
    warnings = []
    land_count = sum(card.qty for card in lands)
    
    warnings.extend(generate_land_warnings(land_count, avg_mv, effective_sources))
    warnings.extend(generate_ramp_warnings(ramp_count, land_count, avg_mv))
    warnings.extend(generate_density_warnings(early_density, mid_density, top_end_density))
    warnings.extend(generate_spikiness_warnings(mv_hist))
    warnings.extend(generate_commander_warnings(context, avg_mv, ramp_count))
    
    # 9. Score components
    mana_score, mana_note = score_mana_support(effective_sources, avg_mv)
    early_score, early_note = score_early_game(early_density)
    top_score, top_note = score_top_end(top_end_density)
    smooth_score, smooth_note = score_smoothness(mv_hist)
    
    total_score = calculate_total_score(mana_score, early_score, top_score, smooth_score)
    
    score_breakdown = {
        "mana_support": mana_score,
        "early_game": early_score,
        "top_end": top_score,
        "smoothness": smooth_score
    }
    
    # 10. Determine curve level
    curve_level = determine_curve_level(avg_mv, early_density, top_end_density, warnings)
    
    # 11. Generate notes
    notes = [mana_note, early_note, top_note, smooth_note]
    
    return CurveEvalResult(
        curve_score=total_score,
        curve_level=curve_level,
        avg_mv=avg_mv,
        median_mv=median_mv,
        mv_hist=mv_hist,
        early_density=early_density,
        mid_density=mid_density,
        top_end_density=top_end_density,
        land_count=land_count,
        ramp_count=ramp_count,
        effective_mana_sources=effective_sources,
        playable_by_turn=playable_by_turn,
        warnings=warnings,
        notes=notes,
        score_breakdown=score_breakdown
    )


# ===== Summary Generation =====

def generate_curve_summary(result: CurveEvalResult) -> str:
    """Generate a human-readable summary of curve analysis"""
    lines = [
        f"Curve Score: {result.curve_score}/100 ({result.curve_level.value.title()})",
        "",
        "Curve Statistics:",
        f"  Average MV: {result.avg_mv:.2f}",
        f"  Median MV: {result.median_mv:.2f}",
        f"  Lands: {result.land_count}",
        f"  Ramp: {result.ramp_count}",
        f"  Effective Sources: {result.effective_mana_sources:.1f}",
        "",
        "Density Distribution:",
        f"  Early Game (MV ≤2): {result.early_density:.1%}",
        f"  Mid Game (MV 3-4): {result.mid_density:.1%}",
        f"  Late Game (MV ≥5): {result.top_end_density:.1%}",
        "",
        "Score Breakdown:",
    ]
    
    for component, score in result.score_breakdown.items():
        lines.append(f"  {component.replace('_', ' ').title()}: {score}")
    
    if result.notes:
        lines.append("")
        lines.append("Analysis:")
        for note in result.notes:
            lines.append(f"  • {note}")
    
    if result.warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in result.warnings:
            lines.append(f"  ⚠ {warning}")
    
    return "\n".join(lines)

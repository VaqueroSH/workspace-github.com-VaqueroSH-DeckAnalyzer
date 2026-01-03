"""
Consistency analysis module for deck evaluation.
Measures how reliably a deck executes its gameplan.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Set, Iterable
import re


class ConsistencyLevel(Enum):
    """Overall consistency rating"""
    VERY_HIGH = "Very High (85-100)"
    HIGH = "High (70-84)"
    MODERATE = "Moderate (50-69)"
    LOW = "Low (30-49)"
    VERY_LOW = "Very Low (0-29)"


@dataclass(frozen=True)
class ConsistencyMetrics:
    """Raw metrics used to calculate consistency"""
    # Access metrics
    tutor_count: int
    draw_engine_count: int
    selection_count: int
    total_access: int
    
    # Redundancy metrics
    role_distribution: Dict[str, int]  # role -> count
    top_role_depth: int  # deepest role stack
    
    # Mana metrics
    land_count: int
    ramp_count: int
    total_mana_sources: int
    avg_cmc: float
    color_intensity: float  # pips vs sources ratio
    
    # Speed metrics
    fast_mana_count: int  # 0-1 CMC ramp
    free_interaction_count: int
    
    # Risk metrics
    high_cmc_percentage: float  # % cards 6+ CMC
    narrow_card_count: int
    commander_dependence: int  # cards that need commander


@dataclass(frozen=True)
class ConsistencyResult:
    """Complete consistency analysis output"""
    score: int  # 0-100
    level: ConsistencyLevel
    metrics: ConsistencyMetrics
    breakdown: Dict[str, int]  # component scores
    strengths: List[str]
    weaknesses: List[str]
    notes: List[str]


# ===== Card Classification Lists =====

# Tutors (direct access)
TUTORS = {
    # Universal
    "demonic tutor", "vampiric tutor", "imperial seal", "grim tutor",
    "diabolic intent", "cruel tutor", "diabolic tutor",
    
    # Conditional tutors
    "enlightened tutor", "mystical tutor", "worldly tutor", "sylvan tutor",
    "gamble", "merchant scroll", "muddle the mixture", "fabricate",
    "whir of invention", "tinker", "tribute mage", "trophy mage",
    "trinket mage", "drift of phantasms", "beseech the queen",
    
    # Creature tutors
    "chord of calling", "green sun's zenith", "natural order",
    "survival of the fittest", "fauna shaman", "crop rotation",
    "summoner's pact", "eldritch evolution", "finale of devastation",
    
    # Artifact tutors
    "inventors' fair", "urza's saga", "reshape", "transmute artifact",
    
    # Land tutors
    "expedition map", "sylvan scrying", "tempt with discovery",
}

# Draw engines (ongoing access)
DRAW_ENGINES = {
    "rhystic study", "mystic remora", "consecrated sphinx", "necropotence",
    "phyrexian arena", "dark confidant", "bob", "sylvan library",
    "the one ring", "esper sentinel", "trouble in pairs", "trouble in pairs",
    "guardian project", "elemental bond", "primordial sage",
    "kindred discovery", "bident of thassa", "coastal piracy",
    "reconnaissance mission", "greed", "arguel's blood fast",
    "dawn of hope", "mentor of the meek", "well of lost dreams",
    "sram, senior edificer", "puresteel paladin", "vedalken archmage",
    "jhoira, weatherlight captain", "the reality chip", "sensei's divining top",
}

# Card selection (filtering)
SELECTION = {
    "ponder", "preordain", "brainstorm", "serum visions", "consider",
    "impulse", "opt", "anticipate", "sleight of hand", "portent",
    "careful study", "faithless looting", "cathartic reunion",
    "thrill of possibility", "compulsive research", "search for azcanta",
    "urza's bauble", "mishra's bauble", "abundant harvest",
    "once upon a time", "oath of nissa", "adventurous impulse",
}

# Fast mana (0-2 CMC ramp)
FAST_MANA = {
    # 0 CMC
    "mana crypt", "mox diamond", "mox opal", "chrome mox", "mox amber",
    "lion's eye diamond", "lotus petal", "jeweled lotus",
    
    # 1 CMC
    "sol ring", "mana vault", "birds of paradise", "llanowar elves",
    "elvish mystic", "fyndhorn elves", "arbor elf", "avacyn's pilgrim",
    "boreal druid", "elves of deep shadow", "deathrite shaman",
    "noble hierarch", "ignoble hierarch", "wild growth", "utopia sprawl",
    
    # 2 CMC
    "arcane signet", "fellwar stone", "grim monolith", "bloom tender",
    "priest of titania", "wirewood channeler", "devoted druid",
    "rofellos, llanowar emissary", "sakura-tribe elder", "three visits",
    "nature's lore", "rampant growth", "farseek", "talisman of progress",
    "talisman of dominance", "talisman of indulgence", "talisman of impulse",
    "talisman of unity", "thought vessel", "mind stone", "coldsteel heart",
    "sphere of the suns",
}

# Free interaction
FREE_INTERACTION = {
    "force of will", "force of negation", "pact of negation", "fierce guardianship",
    "deflecting swat", "flusterstorm", "mental misstep", "commandeer",
    "disrupting shoal", "thwart", "foil", "daze", "submerge",
    "snapback", "slaughter pact", "intervention pact", "summoner's pact",
}


def _canon(name: str) -> str:
    """Canonicalize card name for matching"""
    import unicodedata
    if not name:
        return ""
    name = unicodedata.normalize("NFKD", name)
    name = "".join(ch for ch in name if not unicodedata.combining(ch))
    name = name.casefold()
    name = name.replace("'", "'").replace("'", "'").replace(""", '"').replace(""", '"')
    name = re.sub(r"[^a-z0-9 ,'-]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _count_matches(deck_cards: Iterable[str], reference_set: Set[str]) -> int:
    """Count how many deck cards match a reference set"""
    canon_deck = {_canon(c) for c in deck_cards}
    return len(canon_deck & reference_set)


def _calculate_access_score(metrics: ConsistencyMetrics) -> tuple[int, List[str]]:
    """
    Score card access (tutors, draw, selection).
    Scale: 0-30 points
    """
    score = 0
    notes = []
    
    # Tutors are worth more (direct access)
    tutor_points = min(metrics.tutor_count * 3, 12)
    score += tutor_points
    
    # Draw engines (ongoing access)
    draw_points = min(metrics.draw_engine_count * 2, 10)
    score += draw_points
    
    # Selection (filtering)
    selection_points = min(metrics.selection_count * 1, 8)
    score += selection_points
    
    # Generate notes
    if metrics.total_access >= 15:
        notes.append("Excellent card access - high tutor/draw density")
    elif metrics.total_access >= 10:
        notes.append("Good card access - reliable access to key pieces")
    elif metrics.total_access >= 6:
        notes.append("Moderate card access - some inconsistency expected")
    else:
        notes.append("Low card access - deck relies heavily on topdecks")
    
    return score, notes


def _calculate_redundancy_score(metrics: ConsistencyMetrics, deck_size: int) -> tuple[int, List[str]]:
    """
    Score role redundancy - do you have backup plans?
    Scale: 0-25 points
    """
    score = 0
    notes = []
    
    # Check depth of most common roles
    if metrics.top_role_depth >= 12:
        score += 15
        notes.append("Strong redundancy in key roles")
    elif metrics.top_role_depth >= 8:
        score += 10
        notes.append("Good redundancy in primary strategy")
    elif metrics.top_role_depth >= 5:
        score += 5
        notes.append("Moderate redundancy")
    else:
        notes.append("Low redundancy - vulnerable to disruption")
    
    # Check role diversity (are roles well distributed?)
    num_roles = len(metrics.role_distribution)
    if num_roles >= 8:
        score += 10
        notes.append("Well-rounded role distribution")
    elif num_roles >= 5:
        score += 5
    
    return score, notes


def _calculate_mana_score(metrics: ConsistencyMetrics) -> tuple[int, List[str]]:
    """
    Score mana reliability.
    Scale: 0-25 points
    """
    score = 0
    notes = []
    
    # Land count relative to curve
    expected_lands = 30 + (metrics.avg_cmc - 3.0) * 2
    land_score = 10
    
    if metrics.land_count < expected_lands - 5:
        land_score = 3
        notes.append(f"Low land count ({metrics.land_count}) for average CMC {metrics.avg_cmc:.1f}")
    elif metrics.land_count < expected_lands - 2:
        land_score = 6
        notes.append(f"Below-average land count for curve")
    elif metrics.land_count >= expected_lands:
        notes.append("Appropriate land count for curve")
    
    score += land_score
    
    # Ramp density
    if metrics.ramp_count >= 12:
        score += 10
        notes.append("High ramp density - curve effectively lowered")
    elif metrics.ramp_count >= 8:
        score += 7
        notes.append("Good ramp support")
    elif metrics.ramp_count >= 5:
        score += 4
    else:
        notes.append("Low ramp - mana development may be slow")
    
    # Color intensity check
    if metrics.color_intensity > 1.5:
        score -= 5
        notes.append("High color requirements may cause mana issues")
    
    return score, notes


def _calculate_speed_score(metrics: ConsistencyMetrics) -> tuple[int, List[str]]:
    """
    Score speed enablers (fast mana, free interaction).
    Scale: 0-15 points
    """
    score = 0
    notes = []
    
    # Fast mana
    if metrics.fast_mana_count >= 12:
        score += 10
        notes.append("Exceptional fast mana - very explosive starts possible")
    elif metrics.fast_mana_count >= 8:
        score += 7
        notes.append("Strong fast mana suite")
    elif metrics.fast_mana_count >= 5:
        score += 4
    
    # Free interaction
    if metrics.free_interaction_count >= 5:
        score += 5
        notes.append("High free interaction - can protect combo/tempo with mana up")
    elif metrics.free_interaction_count >= 3:
        score += 3
    
    return score, notes


def _calculate_risk_penalty(metrics: ConsistencyMetrics) -> tuple[int, List[str]]:
    """
    Penalize dead draw risks.
    Scale: 0 to -15 points
    """
    penalty = 0
    notes = []
    
    # Top-heavy curve
    if metrics.high_cmc_percentage > 0.25:
        penalty -= 8
        notes.append("High percentage of expensive spells - may have clunky draws")
    elif metrics.high_cmc_percentage > 0.15:
        penalty -= 4
    
    # Narrow cards
    if metrics.narrow_card_count > 15:
        penalty -= 5
        notes.append("Many situational cards - dead draws likely")
    elif metrics.narrow_card_count > 8:
        penalty -= 2
    
    # Commander dependence
    if metrics.commander_dependence > 20:
        penalty -= 2
        notes.append("Heavy commander dependence - vulnerable to removal")
    
    return penalty, notes


def calculate_consistency(
    deck_cards: List[str],
    role_distribution: Dict[str, int],
    avg_cmc: float,
    land_count: int,
    commander_centric_count: int = 0,
    narrow_card_count: int = 0,
) -> ConsistencyResult:
    """
    Main consistency calculation function.
    
    Args:
        deck_cards: List of all card names in deck
        role_distribution: Dict mapping role names to card counts
        avg_cmc: Average converted mana cost
        land_count: Number of lands
        commander_centric_count: Cards that need commander to work
        narrow_card_count: Cards that are situational/narrow
    """
    
    # Count card categories
    tutor_count = _count_matches(deck_cards, TUTORS)
    draw_count = _count_matches(deck_cards, DRAW_ENGINES)
    selection_count = _count_matches(deck_cards, SELECTION)
    fast_mana_count = _count_matches(deck_cards, FAST_MANA)
    free_int_count = _count_matches(deck_cards, FREE_INTERACTION)
    
    # Calculate ramp (from role distribution or fast mana)
    ramp_count = role_distribution.get("Ramp", 0) + fast_mana_count
    
    # High CMC percentage
    deck_size = len(deck_cards)
    # This would ideally parse CMC from each card, but for now estimate
    high_cmc_count = int(deck_size * 0.15)  # placeholder
    high_cmc_pct = high_cmc_count / deck_size if deck_size > 0 else 0
    
    # Find deepest role
    top_role_depth = max(role_distribution.values()) if role_distribution else 0
    
    # Color intensity (placeholder - would need actual color analysis)
    color_intensity = 1.0  # neutral default
    
    # Build metrics
    metrics = ConsistencyMetrics(
        tutor_count=tutor_count,
        draw_engine_count=draw_count,
        selection_count=selection_count,
        total_access=tutor_count + draw_count + selection_count,
        role_distribution=role_distribution,
        top_role_depth=top_role_depth,
        land_count=land_count,
        ramp_count=ramp_count,
        total_mana_sources=land_count + ramp_count,
        avg_cmc=avg_cmc,
        color_intensity=color_intensity,
        fast_mana_count=fast_mana_count,
        free_interaction_count=free_int_count,
        high_cmc_percentage=high_cmc_pct,
        narrow_card_count=narrow_card_count,
        commander_dependence=commander_centric_count,
    )
    
    # Calculate component scores
    access_score, access_notes = _calculate_access_score(metrics)
    redundancy_score, redundancy_notes = _calculate_redundancy_score(metrics, deck_size)
    mana_score, mana_notes = _calculate_mana_score(metrics)
    speed_score, speed_notes = _calculate_speed_score(metrics)
    risk_penalty, risk_notes = _calculate_risk_penalty(metrics)
    
    # Total score
    total_score = access_score + redundancy_score + mana_score + speed_score + risk_penalty
    total_score = max(0, min(100, total_score))  # clamp to 0-100
    
    # Determine level
    if total_score >= 85:
        level = ConsistencyLevel.VERY_HIGH
    elif total_score >= 70:
        level = ConsistencyLevel.HIGH
    elif total_score >= 50:
        level = ConsistencyLevel.MODERATE
    elif total_score >= 30:
        level = ConsistencyLevel.LOW
    else:
        level = ConsistencyLevel.VERY_LOW
    
    # Collect all notes
    all_notes = access_notes + redundancy_notes + mana_notes + speed_notes + risk_notes
    
    # Identify strengths and weaknesses
    strengths = []
    weaknesses = []
    
    breakdown = {
        "access": access_score,
        "redundancy": redundancy_score,
        "mana": mana_score,
        "speed": speed_score,
        "risk_penalty": risk_penalty,
    }
    
    if access_score >= 20:
        strengths.append("Excellent card access")
    elif access_score < 10:
        weaknesses.append("Limited card access - relies on topdecks")
    
    if redundancy_score >= 18:
        strengths.append("Strong redundancy in key roles")
    elif redundancy_score < 8:
        weaknesses.append("Low redundancy - vulnerable to disruption")
    
    if mana_score >= 18:
        strengths.append("Solid mana base")
    elif mana_score < 10:
        weaknesses.append("Mana base concerns")
    
    if speed_score >= 10:
        strengths.append("Fast mana enables explosive starts")
    
    if risk_penalty < -8:
        weaknesses.append("High risk of dead/clunky draws")
    
    return ConsistencyResult(
        score=total_score,
        level=level,
        metrics=metrics,
        breakdown=breakdown,
        strengths=strengths,
        weaknesses=weaknesses,
        notes=all_notes,
    )


def generate_consistency_summary(result: ConsistencyResult) -> str:
    """Generate a human-readable summary of consistency analysis"""
    lines = [
        f"Consistency Score: {result.score}/100 ({result.level.value})",
        "",
        "Component Breakdown:",
    ]
    
    for component, score in result.breakdown.items():
        lines.append(f"  {component.title()}: {score}")
    
    if result.strengths:
        lines.append("")
        lines.append("Strengths:")
        for s in result.strengths:
            lines.append(f"  ✓ {s}")
    
    if result.weaknesses:
        lines.append("")
        lines.append("Weaknesses:")
        for w in result.weaknesses:
            lines.append(f"  ⚠ {w}")
    
    if result.notes:
        lines.append("")
        lines.append("Analysis Notes:")
        for note in result.notes:
            lines.append(f"  • {note}")
    
    return "\n".join(lines)

"""
Synergy detection module for deck analysis.
Identifies deck strategies and scores how well cards support the plan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set, Any
from collections import defaultdict
import re


# ===== DATA MODELS =====

@dataclass
class SynergySignal:
    """
    A single detected signal from a card.
    Examples: "token_producer", "sac_outlet", "artifact_payoff"
    """
    tag: str
    strength: float  # How loud is this signal (1.0 = baseline)
    evidence: str  # Short explanation for reporting
    source: str  # "oracle", "type_line", "keywords"


@dataclass
class CardSynergyResult:
    """Synergy analysis for a single card"""
    card_name: str
    signals: List[SynergySignal] = field(default_factory=list)
    package_scores: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)


@dataclass
class ComponentCoverage:
    """Coverage for one component of a package"""
    name: str
    count: int
    min_required: int
    weight: float
    coverage_ratio: float  # 0.0 to 1.0+
    score_contribution: float


@dataclass
class PackageResult:
    """Results for one strategy package"""
    name: str
    score: float  # 0-100
    total_signals: float
    components: List[ComponentCoverage]
    missing: List[str]  # Missing component types
    top_cards: List[Tuple[str, float]]  # (card_name, contribution)
    notes: List[str] = field(default_factory=list)


@dataclass
class SynergyReport:
    """Complete synergy analysis"""
    overall_score: float  # 0-100
    primary_packages: List[PackageResult]  # Top 1-3 strategies
    all_packages: List[PackageResult]  # All evaluated packages
    per_card: Dict[str, CardSynergyResult]
    warnings: List[str]
    deck_tag_totals: Dict[str, float]  # For debugging
    

# ===== PACKAGE DEFINITIONS =====

@dataclass
class ComponentRule:
    """Rules for one component of a package"""
    tags: List[str]  # Tags that count for this component
    min_required: int  # Minimum count for good coverage
    weight: float  # Scoring weight
    display_name: str


@dataclass
class SynergyPackageDefinition:
    """Defines a complete strategy package"""
    name: str
    display_name: str
    description: str
    components: Dict[str, ComponentRule]  # e.g., "enablers", "payoffs", "fuel"
    synergy_pairs: List[Tuple[str, str]] = field(default_factory=list)  # Bonus for combinations
    conflict_tags: Set[str] = field(default_factory=set)  # Tags that fight this plan
    max_score: float = 100.0


def get_default_packages() -> List[SynergyPackageDefinition]:
    """
    Returns the standard set of packages supported in V2.
    Each package defines what makes that strategy work.
    """
    packages = []
    
    # ===== ARISTOCRATS (Sacrifice Theme) =====
    packages.append(SynergyPackageDefinition(
        name="aristocrats",
        display_name="Aristocrats",
        description="Sacrifice creatures for value",
        components={
            "outlets": ComponentRule(
                tags=["sac_outlet", "sac_outlet_free"],
                min_required=5,
                weight=1.5,
                display_name="Sacrifice Outlets"
            ),
            "payoffs": ComponentRule(
                tags=["death_payoff", "dies_trigger", "blood_artist_effect"],
                min_required=6,
                weight=1.3,
                display_name="Death Payoffs"
            ),
            "fodder": ComponentRule(
                tags=["token_producer", "cheap_creature", "recursive_creature"],
                min_required=10,
                weight=1.0,
                display_name="Sacrifice Fodder"
            )
        },
        synergy_pairs=[("sac_outlet_free", "death_payoff")],
        conflict_tags={"exile_graveyard", "prevent_death_triggers"}
    ))
    
    # ===== TOKENS (Go-Wide) =====
    packages.append(SynergyPackageDefinition(
        name="tokens",
        display_name="Token Swarm",
        description="Generate and profit from creature tokens",
        components={
            "producers": ComponentRule(
                tags=["token_producer", "token_doubler"],
                min_required=10,
                weight=1.3,
                display_name="Token Producers"
            ),
            "payoffs": ComponentRule(
                tags=["token_payoff", "wide_payoff", "etb_payoff"],
                min_required=6,
                weight=1.5,
                display_name="Token Payoffs"
            ),
            "support": ComponentRule(
                tags=["anthem", "pump_team"],
                min_required=4,
                weight=1.0,
                display_name="Team Buffs"
            )
        },
        synergy_pairs=[("token_doubler", "token_producer")],
        conflict_tags={"boardwipe_nontoken", "massacre"}
    ))
    
    # ===== SPELLSLINGER (Instants/Sorceries Matter) =====
    packages.append(SynergyPackageDefinition(
        name="spellslinger",
        display_name="Spellslinger",
        description="Cast lots of instants and sorceries for value",
        components={
            "spells": ComponentRule(
                tags=["cheap_spell", "cantrip", "ritual"],
                min_required=15,
                weight=1.0,
                display_name="Cheap Spells"
            ),
            "triggers": ComponentRule(
                tags=["spellslinger_trigger", "prowess", "magecraft"],
                min_required=6,
                weight=1.5,
                display_name="Spell Triggers"
            ),
            "payoffs": ComponentRule(
                tags=["spell_payoff", "storm_payoff"],
                min_required=4,
                weight=1.3,
                display_name="Spell Payoffs"
            )
        },
        conflict_tags={"spell_tax_all", "rule_of_law"}
    ))
    
    # ===== ARTIFACTS (Artifact Synergies) =====
    packages.append(SynergyPackageDefinition(
        name="artifacts",
        display_name="Artifacts Matter",
        description="Artifact synergies and engines",
        components={
            "artifacts": ComponentRule(
                tags=["artifact_count", "artifact_creature"],
                min_required=15,
                weight=1.0,
                display_name="Artifact Density"
            ),
            "payoffs": ComponentRule(
                tags=["artifact_payoff", "metalcraft"],
                min_required=6,
                weight=1.5,
                display_name="Artifact Payoffs"
            ),
            "engines": ComponentRule(
                tags=["artifact_engine", "artifact_recursion"],
                min_required=4,
                weight=1.2,
                display_name="Artifact Engines"
            )
        },
        conflict_tags={"destroy_artifacts", "artifact_hate"}
    ))
    
    # ===== ENCHANTRESS (Enchantment Draw) =====
    packages.append(SynergyPackageDefinition(
        name="enchantress",
        display_name="Enchantress",
        description="Enchantment density with draw engines",
        components={
            "enchantments": ComponentRule(
                tags=["enchantment_count"],
                min_required=15,
                weight=1.0,
                display_name="Enchantment Density"
            ),
            "draw": ComponentRule(
                tags=["enchantress_draw"],
                min_required=4,
                weight=2.0,
                display_name="Enchantress Effects"
            ),
            "payoffs": ComponentRule(
                tags=["enchantment_payoff"],
                min_required=4,
                weight=1.3,
                display_name="Enchantment Payoffs"
            )
        }
    ))
    
    # ===== REANIMATOR (Graveyard Recursion) =====
    packages.append(SynergyPackageDefinition(
        name="reanimator",
        display_name="Reanimator",
        description="Fill graveyard and reanimate threats",
        components={
            "fillers": ComponentRule(
                tags=["yard_filler", "self_mill", "discard_outlet"],
                min_required=6,
                weight=1.2,
                display_name="Graveyard Fillers"
            ),
            "reanimation": ComponentRule(
                tags=["reanimate_spell", "recursion"],
                min_required=6,
                weight=1.5,
                display_name="Reanimation Spells"
            ),
            "targets": ComponentRule(
                tags=["reanimate_target", "etb_bomb"],
                min_required=6,
                weight=1.2,
                display_name="Reanimation Targets"
            )
        },
        conflict_tags={"exile_graveyard", "graveyard_hate"}
    ))
    
    # ===== +1/+1 COUNTERS =====
    packages.append(SynergyPackageDefinition(
        name="counters",
        display_name="+1/+1 Counters",
        description="Place and proliferate +1/+1 counters",
        components={
            "sources": ComponentRule(
                tags=["counter_source", "counter_when_etb"],
                min_required=10,
                weight=1.2,
                display_name="Counter Sources"
            ),
            "payoffs": ComponentRule(
                tags=["counter_payoff", "counter_matters"],
                min_required=6,
                weight=1.5,
                display_name="Counter Payoffs"
            ),
            "support": ComponentRule(
                tags=["proliferate", "counter_doubler"],
                min_required=3,
                weight=1.3,
                display_name="Counter Support"
            )
        }
    ))
    
    # ===== VOLTRON (Single Creature Focus) =====
    packages.append(SynergyPackageDefinition(
        name="voltron",
        display_name="Voltron",
        description="Power up one creature for commander damage",
        components={
            "buffs": ComponentRule(
                tags=["equipment", "aura_buff", "pump_single"],
                min_required=10,
                weight=1.5,
                display_name="Buffs & Equipment"
            ),
            "protection": ComponentRule(
                tags=["protection", "hexproof", "indestructible"],
                min_required=6,
                weight=1.3,
                display_name="Protection"
            ),
            "support": ComponentRule(
                tags=["evasion", "double_strike"],
                min_required=4,
                weight=1.0,
                display_name="Evasion & Keywords"
            )
        },
        conflict_tags={"boardwipe", "sacrifice_creature"}
    ))
    
    # ===== LANDFALL =====
    packages.append(SynergyPackageDefinition(
        name="landfall",
        display_name="Landfall",
        description="Trigger landfall for value",
        components={
            "triggers": ComponentRule(
                tags=["landfall", "land_etb_trigger"],
                min_required=8,
                weight=1.5,
                display_name="Landfall Triggers"
            ),
            "ramp": ComponentRule(
                tags=["land_ramp", "fetch_land", "land_recursion"],
                min_required=12,
                weight=1.2,
                display_name="Land Ramp"
            ),
            "payoffs": ComponentRule(
                tags=["landfall_payoff", "land_count_matters"],
                min_required=4,
                weight=1.3,
                display_name="Landfall Payoffs"
            )
        }
    ))
    
    # ===== GROUP SLUG (Damage to All) =====
    packages.append(SynergyPackageDefinition(
        name="group_slug",
        display_name="Group Slug",
        description="Damage all opponents symmetrically",
        components={
            "damage": ComponentRule(
                tags=["group_slug", "damage_all", "drain"],
                min_required=10,
                weight=1.5,
                display_name="Group Damage"
            ),
            "protection": ComponentRule(
                tags=["lifegain", "damage_prevention"],
                min_required=6,
                weight=1.2,
                display_name="Life Protection"
            )
        }
    ))
    
    # ===== STORM/COMBO =====
    packages.append(SynergyPackageDefinition(
        name="storm",
        display_name="Storm/Combo",
        description="Chain spells or infinite combos",
        components={
            "enablers": ComponentRule(
                tags=["ritual", "cost_reducer", "free_spell"],
                min_required=10,
                weight=1.5,
                display_name="Enablers"
            ),
            "draw": ComponentRule(
                tags=["cantrip", "wheel", "draw_engine"],
                min_required=12,
                weight=1.3,
                display_name="Card Draw"
            ),
            "payoffs": ComponentRule(
                tags=["storm_payoff", "combo_piece", "wincon"],
                min_required=4,
                weight=1.5,
                display_name="Win Conditions"
            )
        }
    ))
    
    return packages


# ===== SIGNAL EXTRACTION =====

# Pattern definitions for signal detection
SIGNAL_PATTERNS = {
    # Sacrifice theme
    "sac_outlet": [
        (r"sacrifice (?:a|an|any|another) (?:creature|permanent)", 1.0),
        (r"sacrifice .*:", 1.0),
    ],
    "sac_outlet_free": [
        (r"sacrifice a creature:\s*(?!.*pay|.*{)", 1.5),  # Free sac
    ],
    "death_payoff": [
        (r"whenever (?:a|another) creature (?:you control )?dies", 1.5),
        (r"when .* dies", 1.0),
    ],
    "dies_trigger": [
        (r"when .* dies", 1.0),
        (r"dies trigger", 1.0),
    ],
    "blood_artist_effect": [
        (r"whenever .* dies,.* each opponent", 2.0),
        (r"whenever .* dies,.* target (?:player|opponent)", 1.5),
    ],
    
    # Tokens
    "token_producer": [
        (r"create (?:a|an|one|two|three|four|five|\d+|x) .* token", 1.0),
        (r"put .* token(?:s)? onto the battlefield", 1.0),
    ],
    "token_doubler": [
        (r"if an effect would create .* tokens?.* instead", 2.5),
        (r"(?:double|twice) .*tokens", 2.5),
    ],
    "token_payoff": [
        (r"tokens you control", 1.5),
        (r"for each token", 1.5),
    ],
    "wide_payoff": [
        (r"creatures you control get \+", 1.5),
        (r"each creature you control", 1.3),
        (r"for each creature you control", 1.5),
    ],
    "etb_payoff": [
        (r"whenever (?:a|another) creature enters the battlefield", 1.5),
    ],
    "anthem": [
        (r"creatures you control get \+\d+/\+\d+", 1.5),
        (r"other .* you control get \+", 1.3),
    ],
    
    # Spellslinger
    "cheap_spell": [],  # Detected by CMC <= 2 and instant/sorcery
    "cantrip": [
        (r"draw a card", 1.0),
    ],
    "spellslinger_trigger": [
        (r"whenever you cast (?:an )?instant or sorcery", 2.0),
        (r"whenever you cast .* spell", 1.5),
    ],
    "prowess": [
        (r"prowess", 1.5),
    ],
    "magecraft": [
        (r"magecraft", 2.0),
    ],
    "spell_payoff": [
        (r"for each instant and sorcery", 1.5),
        (r"for each spell", 1.3),
    ],
    "storm_payoff": [
        (r"storm", 3.0),
        (r"for each spell cast", 2.0),
    ],
    
    # Artifacts
    "artifact_count": [],  # Detected by type_line
    "artifact_creature": [],  # Detected by type_line
    "artifact_payoff": [
        (r"artifacts you control", 1.5),
        (r"for each artifact", 1.5),
    ],
    "metalcraft": [
        (r"metalcraft", 2.0),
        (r"if you control three or more artifacts", 1.5),
    ],
    "artifact_engine": [
        (r"whenever .* artifact (?:enters|you control)", 1.5),
    ],
    "artifact_recursion": [
        (r"return .* artifact .* from your graveyard", 1.5),
    ],
    
    # Enchantments
    "enchantment_count": [],  # Detected by type_line
    "enchantress_draw": [
        (r"whenever you cast an enchantment.* draw", 3.0),
        (r"whenever an enchantment enters.* draw", 3.0),
    ],
    "enchantment_payoff": [
        (r"enchantments you control", 1.5),
        (r"for each enchantment", 1.5),
    ],
    
    # Reanimator
    "yard_filler": [
        (r"mill", 1.0),
        (r"put .* cards? .*into your graveyard", 1.0),
    ],
    "self_mill": [
        (r"mill (?:cards|the top)", 1.0),
        (r"put the top .* into your graveyard", 1.0),
    ],
    "discard_outlet": [
        (r"discard a card", 1.0),
    ],
    "reanimate_spell": [
        (r"return target creature card from .* graveyard to the battlefield", 2.0),
        (r"put .* creature card from a graveyard onto the battlefield", 2.0),
    ],
    "reanimate_target": [],  # High CMC creatures
    "etb_bomb": [],  # Creatures with powerful ETBs
    
    # Counters
    "counter_source": [
        (r"put (?:a|an|one|\d+) \+1/\+1 counter", 1.0),
    ],
    "counter_when_etb": [
        (r"enters the battlefield with .* \+1/\+1 counter", 1.5),
    ],
    "counter_payoff": [
        (r"for each \+1/\+1 counter", 1.5),
        (r"with .* \+1/\+1 counters? on", 1.3),
    ],
    "counter_matters": [
        (r"whenever .* \+1/\+1 counter", 1.5),
    ],
    "proliferate": [
        (r"proliferate", 2.0),
    ],
    "counter_doubler": [
        (r"(?:double|twice) .*counters", 2.5),
        (r"if .* would .* counter.* instead", 2.0),
    ],
    
    # Voltron
    "equipment": [],  # Detected by type_line
    "aura_buff": [],  # Auras that grant +X/+X or abilities
    "pump_single": [
        (r"target creature (?:you control )?gets \+", 1.0),
    ],
    "evasion": [
        (r"can't be blocked", 1.5),
        (r"unblockable", 1.5),
        (r"flying", 1.0),
    ],
    "double_strike": [
        (r"double strike", 2.0),
    ],
    
    # Landfall
    "landfall": [
        (r"landfall", 2.0),
    ],
    "land_etb_trigger": [
        (r"whenever a land enters the battlefield", 2.0),
    ],
    "land_ramp": [
        (r"search your library for (?:a|up to) .* land", 1.0),
    ],
    "fetch_land": [
        (r"search your library for a land", 1.5),
    ],
    "land_recursion": [
        (r"return .* land .* from your graveyard", 1.5),
    ],
    "landfall_payoff": [
        (r"for each land you control", 1.5),
    ],
    "land_count_matters": [
        (r"equal to the number of lands you control", 1.5),
    ],
    
    # Group slug
    "group_slug": [
        (r"each (?:player|opponent)", 1.5),
        (r"deals? damage to each opponent", 1.5),
    ],
    "damage_all": [
        (r"each player loses", 1.5),
    ],
    "drain": [
        (r"each opponent loses .* you gain", 2.0),
    ],
    "lifegain": [
        (r"(?:you )?gain .* life", 1.0),
    ],
    
    # Storm/Combo
    "ritual": [
        (r"add {[rgwub]}{[rgwub]}{[rgwub]}", 1.5),
        (r"adds? three mana", 1.5),
    ],
    "cost_reducer": [
        (r"(?:spells|cards) (?:you cast )?cost.* less", 1.5),
    ],
    "free_spell": [
        (r"without paying (?:its|their) mana cost", 2.0),
    ],
    "wheel": [
        (r"each player discards (?:their|his or her) hand.*draws?", 2.5),
    ],
    "draw_engine": [
        (r"whenever .* draw", 2.0),
    ],
    "combo_piece": [
        (r"infinite", 3.0),
        (r"untap all", 1.5),
    ],
    "wincon": [
        (r"you win the game", 3.0),
        (r"target player loses the game", 2.5),
    ],
    
    # Conflict tags
    "boardwipe": [
        (r"destroy all creatures", 1.0),
        (r"exile all creatures", 1.0),
    ],
    "exile_graveyard": [
        (r"exile all cards from all graveyards", 2.0),
        (r"exile target player's graveyard", 1.5),
    ],
    "rule_of_law": [
        (r"each player can't cast more than one spell", 3.0),
    ],
}


def extract_synergy_signals(
    card_name: str,
    type_line: str,
    oracle_text: str,
    keywords: Set[str],
    cmc: float,
    colors: Set[str],
) -> List[SynergySignal]:
    """
    Extract synergy signals from a card.
    
    Args:
        card_name: Card name
        type_line: Type line
        oracle_text: Oracle text
        keywords: Set of keywords
        cmc: Converted mana cost
        colors: Color set
        
    Returns:
        List of detected synergy signals
    """
    signals = []
    text_lower = oracle_text.lower() if oracle_text else ""
    
    # Type-based signals
    if "Artifact" in type_line and "Creature" not in type_line:
        signals.append(SynergySignal(
            tag="artifact_count",
            strength=1.0,
            evidence="Artifact permanent",
            source="type_line"
        ))
        
        if "Equipment" in type_line:
            signals.append(SynergySignal(
                tag="equipment",
                strength=1.5,
                evidence="Equipment type",
                source="type_line"
            ))
    
    if "Artifact" in type_line and "Creature" in type_line:
        signals.append(SynergySignal(
            tag="artifact_creature",
            strength=1.0,
            evidence="Artifact Creature",
            source="type_line"
        ))
        signals.append(SynergySignal(
            tag="artifact_count",
            strength=0.5,
            evidence="Artifact Creature (counts for density)",
            source="type_line"
        ))
    
    if "Enchantment" in type_line:
        signals.append(SynergySignal(
            tag="enchantment_count",
            strength=1.0,
            evidence="Enchantment permanent",
            source="type_line"
        ))
        
        if "Aura" in type_line and any(p in text_lower for p in ["enchanted creature gets", "gets +"]):
            signals.append(SynergySignal(
                tag="aura_buff",
                strength=1.0,
                evidence="Aura that buffs creature",
                source="type_line"
            ))
    
    # CMC-based signals
    if "Instant" in type_line or "Sorcery" in type_line:
        if cmc <= 2:
            signals.append(SynergySignal(
                tag="cheap_spell",
                strength=1.5 if cmc <= 1 else 1.0,
                evidence=f"Cheap instant/sorcery (CMC {cmc})",
                source="cmc"
            ))
    
    # High CMC creatures (reanimator targets)
    if "Creature" in type_line and cmc >= 6:
        signals.append(SynergySignal(
            tag="reanimate_target",
            strength=cmc / 6.0,  # Scale with CMC
            evidence=f"High CMC creature (CMC {cmc})",
            source="cmc"
        ))
        
        # Check for ETB
        if "enters the battlefield" in text_lower:
            signals.append(SynergySignal(
                tag="etb_bomb",
                strength=1.5,
                evidence="High CMC creature with ETB",
                source="oracle"
            ))
    
    # Creature density for aristocrats/tokens
    if "Creature" in type_line and cmc <= 3:
        signals.append(SynergySignal(
            tag="cheap_creature",
            strength=1.0,
            evidence=f"Cheap creature (CMC {cmc})",
            source="cmc"
        ))
    
    # Recursive creatures
    if "Creature" in type_line and any(p in text_lower for p in ["return", "from your graveyard", "unearth", "persist"]):
        signals.append(SynergySignal(
            tag="recursive_creature",
            strength=1.5,
            evidence="Self-recursing creature",
            source="oracle"
        ))
    
    # Pattern-based oracle text detection
    for tag, patterns in SIGNAL_PATTERNS.items():
        for pattern, strength in patterns:
            if re.search(pattern, text_lower):
                # Extract evidence snippet
                match = re.search(pattern, text_lower)
                snippet = match.group(0)[:50] if match else ""  # First 50 chars
                
                signals.append(SynergySignal(
                    tag=tag,
                    strength=strength,
                    evidence=f"Oracle: '{snippet}...'",
                    source="oracle"
                ))
                break  # Only match once per tag
    
    # Keyword-based signals
    for keyword in keywords:
        keyword_lower = keyword.lower()
        if keyword_lower == "flying":
            signals.append(SynergySignal(
                tag="evasion",
                strength=1.0,
                evidence="Has flying",
                source="keywords"
            ))
        elif keyword_lower == "double strike":
            signals.append(SynergySignal(
                tag="double_strike",
                strength=2.0,
                evidence="Has double strike",
                source="keywords"
            ))
        elif keyword_lower in ["hexproof", "shroud"]:
            signals.append(SynergySignal(
                tag="hexproof",
                strength=1.5,
                evidence=f"Has {keyword}",
                source="keywords"
            ))
    
    return signals


def build_deck_signal_index(cards: List[Dict[str, Any]]) -> Dict[str, List[SynergySignal]]:
    """
    Map card_name -> signals for all cards in deck.
    
    Args:
        cards: List of card dictionaries with Scryfall data
        
    Returns:
        Dictionary mapping card name to signals
    """
    index = {}
    
    for card in cards:
        name = card.get('name', '')
        type_line = card.get('type_line', '')
        oracle_text = card.get('oracle_text', '')
        keywords = set(card.get('keywords', []))
        cmc = float(card.get('cmc', 0))
        colors = set(card.get('colors', []))
        
        signals = extract_synergy_signals(name, type_line, oracle_text, keywords, cmc, colors)
        index[name] = signals
    
    return index


def aggregate_tag_counts(
    deck_signals: Dict[str, List[SynergySignal]],
    counts: Dict[str, int]
) -> Dict[str, float]:
    """
    Roll up tag strength across deck (respecting card quantities).
    
    Args:
        deck_signals: Card name -> signals mapping
        counts: Card name -> quantity mapping
        
    Returns:
        Dictionary of tag -> total weighted strength
    """
    tag_totals = defaultdict(float)
    
    for card_name, signals in deck_signals.items():
        qty = counts.get(card_name, 1)
        
        for signal in signals:
            tag_totals[signal.tag] += signal.strength * qty
    
    return dict(tag_totals)


# ===== PACKAGE SCORING =====

def score_package(
    pkg: SynergyPackageDefinition,
    deck_tag_totals: Dict[str, float],
    deck_card_signals: Dict[str, List[SynergySignal]],
    counts: Dict[str, int],
) -> PackageResult:
    """
    Score one strategy package.
    
    Args:
        pkg: Package definition
        deck_tag_totals: Aggregated tag totals
        deck_card_signals: Per-card signals
        counts: Card quantities
        
    Returns:
        PackageResult with score and breakdown
    """
    components = []
    total_score = 0.0
    max_possible = 0.0
    missing = []
    
    # Calculate component coverage
    for comp_name, comp_rule in pkg.components.items():
        # Count how many cards have any of this component's tags
        count = 0.0
        for tag in comp_rule.tags:
            count += deck_tag_totals.get(tag, 0.0)
        
        # Calculate coverage ratio
        coverage_ratio = min(1.0, count / comp_rule.min_required) if comp_rule.min_required > 0 else 1.0
        
        # Calculate score contribution
        score_contribution = coverage_ratio * comp_rule.weight * 25  # Max 25 pts per component
        
        total_score += score_contribution
        max_possible += comp_rule.weight * 25
        
        components.append(ComponentCoverage(
            name=comp_name,
            count=int(count),
            min_required=comp_rule.min_required,
            weight=comp_rule.weight,
            coverage_ratio=coverage_ratio,
            score_contribution=score_contribution
        ))
        
        # Track missing components
        if coverage_ratio < 0.8:  # Less than 80% coverage
            missing.append(comp_rule.display_name)
    
    # Normalize to 0-100
    final_score = (total_score / max_possible * 100) if max_possible > 0 else 0.0
    final_score = min(100.0, final_score)
    
    # Calculate total signal strength for this package
    relevant_tags = set()
    for comp_rule in pkg.components.values():
        relevant_tags.update(comp_rule.tags)
    
    total_signals = sum(deck_tag_totals.get(tag, 0.0) for tag in relevant_tags)
    
    # Notes
    notes = []
    if final_score >= 75:
        notes.append("Strong package - core strategy is well-supported")
    elif final_score >= 50:
        notes.append("Moderate package - strategy is present but could be deeper")
    elif final_score >= 25:
        notes.append("Weak package - strategy is hinted at but underdeveloped")
    else:
        notes.append("Package not present in meaningful amounts")
    
    return PackageResult(
        name=pkg.name,
        score=final_score,
        total_signals=total_signals,
        components=components,
        missing=missing,
        top_cards=[],  # Filled in later
        notes=notes
    )


def pick_primary_packages(all_pkg_results: List[PackageResult], top_n: int = 3) -> List[PackageResult]:
    """
    Decide the deck's main strategies (usually top 1-3 packages).
    
    Args:
        all_pkg_results: All evaluated packages
        top_n: Number of primary packages to return
        
    Returns:
        List of top packages sorted by score
    """
    # Sort by score descending
    sorted_packages = sorted(all_pkg_results, key=lambda p: p.score, reverse=True)
    
    # Only keep packages with meaningful scores
    primary = [p for p in sorted_packages[:top_n] if p.score >= 30]
    
    return primary


# ===== PER-CARD CONTRIBUTION =====

def compute_per_card_package_scores(
    packages: List[SynergyPackageDefinition],
    deck_card_signals: Dict[str, List[SynergySignal]],
    counts: Dict[str, int],
) -> Dict[str, CardSynergyResult]:
    """
    For each card, compute how much it helps each package.
    
    Args:
        packages: Package definitions
        deck_card_signals: Per-card signals
        counts: Card quantities
        
    Returns:
        Dictionary of card name -> CardSynergyResult
    """
    results = {}
    
    for card_name, signals in deck_card_signals.items():
        card_result = CardSynergyResult(card_name=card_name, signals=signals)
        
        for pkg in packages:
            # Collect relevant tags for this package
            relevant_tags = set()
            for comp_rule in pkg.components.values():
                relevant_tags.update(comp_rule.tags)
            
            # Calculate card's contribution to this package
            contribution = 0.0
            for signal in signals:
                if signal.tag in relevant_tags:
                    contribution += signal.strength
            
            if contribution > 0:
                card_result.package_scores[pkg.name] = contribution
        
        results[card_name] = card_result
    
    return results


def rank_top_cards_for_package(
    pkg_name: str,
    per_card: Dict[str, CardSynergyResult],
    limit: int = 10,
) -> List[Tuple[str, float]]:
    """
    Return the top contributing cards for a given package.
    
    Args:
        pkg_name: Package name
        per_card: Per-card synergy results
        limit: Maximum cards to return
        
    Returns:
        List of (card_name, contribution) tuples
    """
    contributions = []
    
    for card_name, result in per_card.items():
        score = result.package_scores.get(pkg_name, 0.0)
        if score > 0:
            contributions.append((card_name, score))
    
    # Sort by contribution descending
    contributions.sort(key=lambda x: -x[1])
    
    return contributions[:limit]


# ===== CONFLICT DETECTION & WARNINGS =====

def detect_synergy_conflicts(
    chosen_packages: List[PackageResult],
    deck_tag_totals: Dict[str, float],
    package_defs: List[SynergyPackageDefinition],
) -> List[str]:
    """
    Detect anti-synergy and conflicting strategies.
    
    Args:
        chosen_packages: Primary packages identified
        deck_tag_totals: Aggregated tags
        package_defs: Package definitions
        
    Returns:
        List of warning strings
    """
    warnings = []
    
    # Map package names to definitions
    pkg_map = {p.name: p for p in package_defs}
    
    for pkg_result in chosen_packages:
        pkg_def = pkg_map.get(pkg_result.name)
        if not pkg_def:
            continue
        
        # Check for conflict tags
        for conflict_tag in pkg_def.conflict_tags:
            if deck_tag_totals.get(conflict_tag, 0.0) >= 2.0:
                warnings.append(
                    f"{pkg_def.display_name} package conflicts with '{conflict_tag}' cards in deck"
                )
    
    # Check for orphan high-cost cards in spellslinger
    if any(p.name == "spellslinger" for p in chosen_packages):
        high_cmc_spells = deck_tag_totals.get("expensive_spell", 0.0)
        if high_cmc_spells > 10:
            warnings.append(
                "Spellslinger deck has many expensive spells - may struggle to chain casts"
            )
    
    # Check for token deck without protection
    if any(p.name == "tokens" for p in chosen_packages):
        boardwipes = deck_tag_totals.get("boardwipe", 0.0)
        if boardwipes > 3:
            warnings.append(
                "Token strategy vulnerable - deck runs multiple boardwipes without token protection"
            )
    
    return warnings


def detect_orphan_payoffs(
    deck_tag_totals: Dict[str, float],
    threshold: float = 4.0,
) -> List[str]:
    """
    Catch payoffs without enablers (or vice versa).
    
    Args:
        deck_tag_totals: Aggregated tag totals
        threshold: Minimum ratio to trigger warning
        
    Returns:
        List of warning strings
    """
    warnings = []
    
    # Define enabler/payoff pairs
    pairs = [
        ("artifact_payoff", "artifact_count", "artifact", "artifacts"),
        ("token_payoff", "token_producer", "token payoff", "token producers"),
        ("spell_payoff", "cheap_spell", "spell payoff", "cheap spells"),
        ("death_payoff", "sac_outlet", "death payoff", "sacrifice outlets"),
        ("counter_payoff", "counter_source", "counter payoff", "counter sources"),
    ]
    
    for payoff_tag, enabler_tag, payoff_name, enabler_name in pairs:
        payoff_count = deck_tag_totals.get(payoff_tag, 0.0)
        enabler_count = deck_tag_totals.get(enabler_tag, 0.0)
        
        if payoff_count >= threshold and enabler_count < threshold:
            warnings.append(
                f"High {payoff_name} count ({payoff_count:.0f}) but low {enabler_name} ({enabler_count:.0f}) - payoffs may underperform"
            )
        elif enabler_count >= threshold * 2 and payoff_count < 2:
            warnings.append(
                f"Many {enabler_name} ({enabler_count:.0f}) but few ways to capitalize - consider more payoffs"
            )
    
    return warnings


# ===== MAIN ENTRY POINT =====

def evaluate_synergy(
    deck_cards: List[Dict[str, Any]],
    counts: Dict[str, int],
    commander_cards: Optional[List[Dict[str, Any]]] = None,
    packages: Optional[List[SynergyPackageDefinition]] = None,
) -> SynergyReport:
    """
    Full synergy evaluation pipeline.
    
    Args:
        deck_cards: List of card dictionaries (Scryfall format)
        counts: Card name -> quantity mapping
        commander_cards: Optional list of commander cards
        packages: Optional custom packages (uses defaults if None)
        
    Returns:
        Complete SynergyReport
    """
    if packages is None:
        packages = get_default_packages()
    
    # 1) Build signals
    deck_signals = build_deck_signal_index(deck_cards)
    
    # 2) Aggregate tags
    deck_tag_totals = aggregate_tag_counts(deck_signals, counts)
    
    # 3) Score all packages
    all_package_results = []
    for pkg in packages:
        result = score_package(pkg, deck_tag_totals, deck_signals, counts)
        all_package_results.append(result)
    
    # 4) Pick primary packages
    primary_packages = pick_primary_packages(all_package_results, top_n=3)
    
    # 5) Per-card scoring
    per_card = compute_per_card_package_scores(packages, deck_signals, counts)
    
    # 6) Fill in top cards for primary packages
    for pkg_result in primary_packages:
        pkg_result.top_cards = rank_top_cards_for_package(pkg_result.name, per_card, limit=10)
    
    # 7) Warnings/conflicts
    warnings = []
    warnings.extend(detect_synergy_conflicts(primary_packages, deck_tag_totals, packages))
    warnings.extend(detect_orphan_payoffs(deck_tag_totals))
    
    # 8) Compute overall score
    # Average of top 2 primary packages (if present)
    if len(primary_packages) >= 2:
        overall_score = (primary_packages[0].score + primary_packages[1].score) / 2
    elif len(primary_packages) == 1:
        overall_score = primary_packages[0].score
    else:
        overall_score = 0.0
    
    return SynergyReport(
        overall_score=overall_score,
        primary_packages=primary_packages,
        all_packages=all_package_results,
        per_card=per_card,
        warnings=warnings,
        deck_tag_totals=deck_tag_totals
    )


# ===== REPORTING =====

def generate_synergy_summary(report: SynergyReport) -> str:
    """Generate human-readable synergy summary"""
    lines = [
        f"Synergy Score: {report.overall_score:.1f}/100",
        "",
        "Primary Strategies:",
    ]
    
    for pkg in report.primary_packages:
        lines.append(f"\n{pkg.name.upper()} ({pkg.score:.1f}/100)")
        lines.append(f"  Total signals: {pkg.total_signals:.1f}")
        
        for comp in pkg.components:
            status = "✓" if comp.coverage_ratio >= 0.8 else "⚠"
            lines.append(
                f"  {status} {comp.name}: {comp.count}/{comp.min_required} "
                f"({comp.coverage_ratio:.0%} coverage)"
            )
        
        if pkg.missing:
            lines.append(f"  Missing: {', '.join(pkg.missing)}")
        
        if pkg.top_cards:
            lines.append("  Top cards:")
            for card_name, contribution in pkg.top_cards[:5]:
                lines.append(f"    • {card_name} ({contribution:.1f})")
    
    if report.warnings:
        lines.append("\nWarnings:")
        for warning in report.warnings:
            lines.append(f"  ⚠ {warning}")
    
    return "\n".join(lines)

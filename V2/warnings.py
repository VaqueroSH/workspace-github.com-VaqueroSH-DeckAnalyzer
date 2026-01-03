"""
Unified warning system for deck analysis.
Aggregates warnings from all analysis modules and detects problematic patterns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Set, Any
from collections import defaultdict
from enum import Enum


class Severity(Enum):
    """Warning severity levels"""
    INFO = "info"  # Notable but not necessarily a problem
    WARN = "warn"  # Likely to cause performance issues
    HIGH = "high"  # Likely to create non-games or major mismatch
    CRITICAL = "critical"  # Violates bracket rules or deck is illegal


@dataclass(frozen=True)
class WarningItem:
    """A single warning with structured data"""
    code: str  # Stable ID: "LOW_LAND_COUNT"
    severity: Severity
    title: str  # Human readable title
    detail: str  # Human readable detail
    evidence: List[str] = field(default_factory=list)  # Card names, counts, snippets
    tags: List[str] = field(default_factory=list)  # ["mana", "stax", "combo", "bracket"]
    suggestion: Optional[str] = None  # Optional fix suggestion


@dataclass
class WarningsReport:
    """Collection of all warnings"""
    items: List[WarningItem]
    
    def by_severity(self) -> Dict[Severity, List[WarningItem]]:
        """Group warnings by severity"""
        out: Dict[Severity, List[WarningItem]] = defaultdict(list)
        for w in self.items:
            out[w.severity].append(w)
        return dict(out)
    
    def by_tag(self) -> Dict[str, List[WarningItem]]:
        """Group warnings by tag"""
        out: Dict[str, List[WarningItem]] = defaultdict(list)
        for w in self.items:
            for tag in w.tags:
                out[tag].append(w)
        return dict(out)
    
    def get_critical(self) -> List[WarningItem]:
        """Get only critical warnings"""
        return [w for w in self.items if w.severity == Severity.CRITICAL]
    
    def get_high(self) -> List[WarningItem]:
        """Get high and critical warnings"""
        return [w for w in self.items if w.severity in (Severity.CRITICAL, Severity.HIGH)]


@dataclass
class WarningContext:
    """Context data for warning evaluation"""
    # Deck basics
    bracket_target: Optional[str]  # "B1", "B2", "B3", "B4", "cEDH"
    deck_size: int
    commanders: List[str]
    
    # Card counts (from roles/tags)
    land_count: int
    ramp_count: int
    interaction_count: int
    removal_count: int
    boardwipe_count: int
    counterspell_count: int
    tutor_count: int
    draw_count: int
    protection_count: int
    
    # Problematic cards (detected by patterns)
    game_changers: List[str] = field(default_factory=list)
    fast_mana: List[str] = field(default_factory=list)
    extra_turns: List[str] = field(default_factory=list)
    mld: List[str] = field(default_factory=list)
    stax_pieces: List[str] = field(default_factory=list)
    free_counters: List[str] = field(default_factory=list)
    infinite_combos: List[str] = field(default_factory=list)
    deterministic_wins: List[str] = field(default_factory=list)
    
    # Reports from other modules
    curve_report: Optional[Any] = None
    roles_summary: Optional[Any] = None
    synergy_report: Optional[Any] = None
    consistency_result: Optional[Any] = None
    
    # Additional metrics
    avg_cmc: float = 0.0
    tapland_count: int = 0
    color_intensity: float = 0.0  # Pips per mana source


# Type for warning rules
WarningRule = Callable[[WarningContext], List[WarningItem]]


# ===== KNOWN PROBLEMATIC CARDS =====

# Fast mana (0-1 CMC)
FAST_MANA_CARDS = {
    "mana crypt", "jeweled lotus", "chrome mox", "mox diamond", "mox opal",
    "mox amber", "lion's eye diamond", "lotus petal", "sol ring", "mana vault",
    "ancient tomb", "grim monolith", "simian spirit guide", "elvish spirit guide"
}

# Extra turns
EXTRA_TURN_CARDS = {
    "time warp", "temporal manipulation", "time stretch", "capture of jingzhou",
    "temporal mastery", "walk the aeons", "expropriate", "nexus of fate",
    "alrund's epiphany", "time walk", "timetwister", "karn's temporal sundering"
}

# Mass land destruction
MLD_CARDS = {
    "armageddon", "ravages of war", "jokulhaups", "obliterate", "decree of annihilation",
    "worldfire", "sunder", "boom // bust", "limited resources", "fall of the thran",
    "wake of destruction", "ruination", "blood moon", "magus of the moon"
}

# Hard stax pieces
STAX_CARDS = {
    "winter orb", "static orb", "tangle wire", "smokestack", "root maze",
    "trinisphere", "lodestone golem", "sphere of resistance", "thorn of amethyst",
    "rule of law", "arcane laboratory", "eidolon of rhetoric", "deafening silence",
    "collector ouphe", "null rod", "stony silence", "torpor orb", "hushbringer",
    "grand arbiter augustin iv", "drannith magistrate", "knowledge pool"
}

# Free interaction
FREE_INTERACTION_CARDS = {
    "force of will", "force of negation", "fierce guardianship", "deflecting swat",
    "pact of negation", "commandeer", "disrupting shoal", "foil", "thwart"
}

# Infinite combo enablers
INFINITE_COMBO_CARDS = {
    "thoracle", "thassa's oracle", "underworld breach", "dockside extortionist",
    "worldgorger dragon", "animate dead", "dance of the dead", "necromancy",
    "isochron scepter", "dramatic reversal", "food chain", "squee, the immortal"
}


def normalize_card_name(name: str) -> str:
    """Normalize card name for comparison"""
    return name.lower().strip()


# ===== BRACKET ENFORCEMENT RULES =====

def rule_bracket_game_changers(ctx: WarningContext) -> List[WarningItem]:
    """Check Game Changer compliance with bracket"""
    if not ctx.bracket_target or not ctx.game_changers:
        return []
    
    warnings = []
    bracket = ctx.bracket_target.upper()
    gc_count = len(ctx.game_changers)
    
    if bracket in ("B1", "B2") and gc_count > 0:
        warnings.append(WarningItem(
            code="BRACKET_GC_NOT_ALLOWED",
            severity=Severity.CRITICAL,
            title="Game Changers not allowed in Bracket 1/2",
            detail=f"Detected {gc_count} Game Changer(s). Bracket 1/2 allows zero.",
            evidence=ctx.game_changers[:12],
            tags=["bracket", "game_changer"],
            suggestion="Remove all Game Changers or move to Bracket 3+"
        ))
    
    elif bracket == "B3" and gc_count > 3:
        warnings.append(WarningItem(
            code="BRACKET_GC_OVER_LIMIT",
            severity=Severity.HIGH,
            title="Too many Game Changers for Bracket 3",
            detail=f"Detected {gc_count} Game Changers. Bracket 3 allows up to 3.",
            evidence=ctx.game_changers[:12],
            tags=["bracket", "game_changer"],
            suggestion=f"Remove {gc_count - 3} Game Changers or move to Bracket 4"
        ))
    
    return warnings


def rule_bracket_fast_mana_density(ctx: WarningContext) -> List[WarningItem]:
    """Flag high fast mana density for casual brackets"""
    if not ctx.bracket_target or not ctx.fast_mana:
        return []
    
    warnings = []
    bracket = ctx.bracket_target.upper()
    fast_count = len(ctx.fast_mana)
    
    if bracket in ("B1", "B2") and fast_count >= 5:
        warnings.append(WarningItem(
            code="BRACKET_HIGH_FAST_MANA",
            severity=Severity.WARN,
            title="High fast mana density for casual bracket",
            detail=f"{fast_count} fast mana sources may be too explosive for Bracket {bracket[-1]}.",
            evidence=ctx.fast_mana[:8],
            tags=["bracket", "mana", "power_level"],
            suggestion="Consider slower ramp options for lower brackets"
        ))
    
    return warnings


def rule_bracket_tutor_density(ctx: WarningContext) -> List[WarningItem]:
    """Flag high tutor density for casual brackets"""
    if not ctx.bracket_target:
        return []
    
    warnings = []
    bracket = ctx.bracket_target.upper()
    
    if bracket in ("B1", "B2") and ctx.tutor_count >= 8:
        warnings.append(WarningItem(
            code="BRACKET_HIGH_TUTOR_DENSITY",
            severity=Severity.WARN,
            title="High tutor density for casual bracket",
            detail=f"{ctx.tutor_count} tutors creates high consistency that may exceed Bracket {bracket[-1]} expectations.",
            evidence=[f"{ctx.tutor_count} tutors in deck"],
            tags=["bracket", "consistency", "power_level"],
            suggestion="Consider reducing tutors or moving to higher bracket"
        ))
    
    return warnings


# ===== MANA BASE SANITY RULES =====

def rule_low_land_count(ctx: WarningContext) -> List[WarningItem]:
    """Flag low land counts"""
    warnings = []
    
    if ctx.land_count < 30:
        warnings.append(WarningItem(
            code="VERY_LOW_LAND_COUNT",
            severity=Severity.HIGH,
            title="Very low land count",
            detail=f"{ctx.land_count} lands is likely to cause frequent mana issues and mulligans.",
            evidence=[f"Lands: {ctx.land_count}"],
            tags=["mana", "consistency"],
            suggestion="Add at least 30-32 lands unless running extreme fast mana"
        ))
    elif ctx.land_count < 32:
        warnings.append(WarningItem(
            code="LOW_LAND_COUNT",
            severity=Severity.WARN,
            title="Low land count",
            detail=f"{ctx.land_count} lands may cause missed land drops unless curve is very low.",
            evidence=[f"Lands: {ctx.land_count}"],
            tags=["mana", "consistency"],
            suggestion="Consider 32-34 lands for more consistent mana"
        ))
    
    return warnings


def rule_insufficient_ramp(ctx: WarningContext) -> List[WarningItem]:
    """Flag insufficient ramp for curve"""
    warnings = []
    
    # Expected ramp based on curve
    if ctx.avg_cmc <= 2.5:
        expected = 8
    elif ctx.avg_cmc <= 3.0:
        expected = 10
    elif ctx.avg_cmc <= 3.4:
        expected = 12
    else:
        expected = 14
    
    if ctx.ramp_count < expected - 3:
        warnings.append(WarningItem(
            code="INSUFFICIENT_RAMP",
            severity=Severity.WARN,
            title="Insufficient ramp for curve",
            detail=f"Average CMC {ctx.avg_cmc:.2f} typically needs {expected}+ ramp sources, but only {ctx.ramp_count} found.",
            evidence=[f"Ramp: {ctx.ramp_count}, Avg CMC: {ctx.avg_cmc:.2f}"],
            tags=["mana", "curve", "consistency"],
            suggestion=f"Add {expected - ctx.ramp_count} more ramp sources"
        ))
    
    return warnings


def rule_too_many_taplands(ctx: WarningContext) -> List[WarningItem]:
    """Flag excessive taplands"""
    warnings = []
    
    if ctx.tapland_count > 8:
        warnings.append(WarningItem(
            code="EXCESSIVE_TAPLANDS",
            severity=Severity.WARN,
            title="High tapland count",
            detail=f"{ctx.tapland_count} taplands will slow down your gameplan significantly.",
            evidence=[f"Taplands: {ctx.tapland_count}"],
            tags=["mana", "speed"],
            suggestion="Replace taplands with basics or untapped duals"
        ))
    
    return warnings


def rule_color_intensity(ctx: WarningContext) -> List[WarningItem]:
    """Flag high color intensity vs fixing"""
    warnings = []
    
    if ctx.color_intensity > 1.5:
        warnings.append(WarningItem(
            code="HIGH_COLOR_INTENSITY",
            severity=Severity.WARN,
            title="High color requirements",
            detail=f"Color intensity ({ctx.color_intensity:.1f} pips per source) may cause color screw.",
            evidence=[f"Color intensity: {ctx.color_intensity:.1f}"],
            tags=["mana", "consistency"],
            suggestion="Add more color fixing or reduce pip-heavy cards"
        ))
    
    return warnings


# ===== SALT/SOCIAL CONTRACT RULES =====

def rule_mass_land_destruction(ctx: WarningContext) -> List[WarningItem]:
    """Flag MLD effects"""
    warnings = []
    
    if ctx.mld:
        severity = Severity.HIGH if len(ctx.mld) > 1 else Severity.WARN
        warnings.append(WarningItem(
            code="MLD_PRESENT",
            severity=severity,
            title="Mass land destruction detected",
            detail=f"{len(ctx.mld)} MLD effect(s) found. These often create non-games at casual tables.",
            evidence=ctx.mld[:8],
            tags=["salt", "mld", "social"],
            suggestion="Confirm your playgroup is okay with MLD before bringing this deck"
        ))
    
    return warnings


def rule_extra_turns(ctx: WarningContext) -> List[WarningItem]:
    """Flag extra turn spells"""
    warnings = []
    
    if len(ctx.extra_turns) >= 3:
        warnings.append(WarningItem(
            code="EXTRA_TURN_CHAIN",
            severity=Severity.HIGH,
            title="Multiple extra turn spells",
            detail=f"{len(ctx.extra_turns)} extra turn spells can lead to long non-interactive turns.",
            evidence=ctx.extra_turns[:8],
            tags=["salt", "extra_turns", "social"],
            suggestion="Consider reducing extra turns or confirming playgroup acceptance"
        ))
    elif ctx.extra_turns:
        warnings.append(WarningItem(
            code="EXTRA_TURN_PRESENT",
            severity=Severity.INFO,
            title="Extra turn spell detected",
            detail=f"{len(ctx.extra_turns)} extra turn spell(s) present.",
            evidence=ctx.extra_turns[:8],
            tags=["salt", "extra_turns"]
        ))
    
    return warnings


def rule_heavy_stax(ctx: WarningContext) -> List[WarningItem]:
    """Flag stax pieces"""
    warnings = []
    
    if len(ctx.stax_pieces) >= 6:
        warnings.append(WarningItem(
            code="HEAVY_STAX",
            severity=Severity.HIGH,
            title="Heavy stax presence",
            detail=f"{len(ctx.stax_pieces)} stax pieces can create slow, frustrating games.",
            evidence=ctx.stax_pieces[:10],
            tags=["salt", "stax", "social"],
            suggestion="Confirm your playgroup enjoys stax gameplay"
        ))
    elif len(ctx.stax_pieces) >= 3:
        warnings.append(WarningItem(
            code="MODERATE_STAX",
            severity=Severity.WARN,
            title="Stax elements present",
            detail=f"{len(ctx.stax_pieces)} stax pieces may slow down games significantly.",
            evidence=ctx.stax_pieces[:10],
            tags=["stax", "social"]
        ))
    
    return warnings


# ===== COMBO/WIN CONDITION RULES =====

def rule_deterministic_combo(ctx: WarningContext) -> List[WarningItem]:
    """Flag deterministic combos"""
    warnings = []
    
    if ctx.deterministic_wins:
        # Check if easily tutored
        easily_tutored = ctx.tutor_count >= 6
        
        severity = Severity.HIGH if easily_tutored else Severity.WARN
        detail = f"Deterministic combo found. {'Easily tutorable' if easily_tutored else 'May be inconsistent'}."
        
        warnings.append(WarningItem(
            code="DETERMINISTIC_COMBO",
            severity=severity,
            title="Deterministic combo present",
            detail=detail,
            evidence=ctx.deterministic_wins[:8],
            tags=["combo", "power_level"],
            suggestion="Ensure combo matches your playgroup's power level expectations"
        ))
    
    return warnings


def rule_few_wincons(ctx: WarningContext) -> List[WarningItem]:
    """Flag decks with too few win conditions"""
    warnings = []
    
    # This would ideally come from synergy/roles
    # For now, just a placeholder check
    if ctx.synergy_report:
        # Check if synergy detected any wincon packages
        pass
    
    return warnings


# ===== INTERACTION DENSITY RULES =====

def rule_low_interaction(ctx: WarningContext) -> List[WarningItem]:
    """Flag low interaction counts"""
    warnings = []
    
    total_interaction = ctx.interaction_count
    
    if total_interaction < 8:
        warnings.append(WarningItem(
            code="LOW_INTERACTION",
            severity=Severity.WARN,
            title="Low interaction count",
            detail=f"Only {total_interaction} interaction pieces. Deck may struggle to answer threats.",
            evidence=[f"Total interaction: {total_interaction}"],
            tags=["interaction", "gameplay"],
            suggestion="Add more removal, counters, or board wipes (aim for 10-12 total)"
        ))
    
    if ctx.removal_count < 5:
        warnings.append(WarningItem(
            code="LOW_REMOVAL",
            severity=Severity.INFO,
            title="Low removal count",
            detail=f"Only {ctx.removal_count} removal spells. May struggle with problematic permanents.",
            evidence=[f"Removal: {ctx.removal_count}"],
            tags=["interaction"],
            suggestion="Consider 6-8 removal spells for consistent answers"
        ))
    
    return warnings


def rule_no_board_wipes(ctx: WarningContext) -> List[WarningItem]:
    """Flag decks with no board wipes"""
    warnings = []
    
    if ctx.boardwipe_count == 0 and ctx.avg_cmc > 3.5:
        warnings.append(WarningItem(
            code="NO_BOARDWIPES",
            severity=Severity.INFO,
            title="No board wipes detected",
            detail="Slower decks typically benefit from 1-2 board wipes as a reset button.",
            evidence=[f"Board wipes: {ctx.boardwipe_count}"],
            tags=["interaction"],
            suggestion="Consider 1-2 board wipes for go-wide strategies"
        ))
    
    return warnings


# ===== CONSISTENCY HAZARD RULES =====

def rule_top_heavy_without_ramp(ctx: WarningContext) -> List[WarningItem]:
    """Flag top-heavy curves without adequate ramp"""
    warnings = []
    
    if ctx.avg_cmc > 3.5 and ctx.ramp_count < 12:
        warnings.append(WarningItem(
            code="TOP_HEAVY_LOW_RAMP",
            severity=Severity.WARN,
            title="Top-heavy curve without adequate ramp",
            detail=f"Average CMC {ctx.avg_cmc:.2f} with only {ctx.ramp_count} ramp sources will be very slow.",
            evidence=[f"Avg CMC: {ctx.avg_cmc:.2f}", f"Ramp: {ctx.ramp_count}"],
            tags=["curve", "mana", "consistency"],
            suggestion="Add more ramp or lower your curve"
        ))
    
    return warnings


def rule_low_card_advantage(ctx: WarningContext) -> List[WarningItem]:
    """Flag low card draw"""
    warnings = []
    
    if ctx.draw_count < 6:
        warnings.append(WarningItem(
            code="LOW_CARD_DRAW",
            severity=Severity.WARN,
            title="Low card draw",
            detail=f"Only {ctx.draw_count} draw sources. May run out of gas in longer games.",
            evidence=[f"Draw sources: {ctx.draw_count}"],
            tags=["consistency", "card_advantage"],
            suggestion="Add 8-10 card draw effects for better late-game resilience"
        ))
    
    return warnings


# ===== INTEGRATION WITH OTHER MODULES =====

def rule_consistency_warnings(ctx: WarningContext) -> List[WarningItem]:
    """Import warnings from consistency module"""
    warnings = []
    
    if ctx.consistency_result:
        # Check consistency score
        if ctx.consistency_result.score < 40:
            reasons = []
            if ctx.consistency_result.metrics.total_access < 8:
                reasons.append("low card access (tutors/draw)")
            if ctx.consistency_result.metrics.top_role_depth < 5:
                reasons.append("low redundancy")
            if ctx.consistency_result.metrics.effective_mana_sources < 38:
                reasons.append("insufficient mana")
            
            warnings.append(WarningItem(
                code="LOW_CONSISTENCY",
                severity=Severity.WARN,
                title="Low consistency score",
                detail=f"Consistency score of {ctx.consistency_result.score}/100 suggests unreliable execution. Issues: {', '.join(reasons)}.",
                evidence=[],
                tags=["consistency"],
                suggestion="Improve card access, redundancy, or mana base"
            ))
    
    return warnings


def rule_curve_warnings(ctx: WarningContext) -> List[WarningItem]:
    """Import warnings from curve module"""
    warnings = []
    
    if ctx.curve_report and hasattr(ctx.curve_report, 'warnings'):
        # Convert curve warnings to WarningItem format
        for curve_warning in ctx.curve_report.warnings:
            # Determine severity from content
            severity = Severity.WARN
            if "very" in curve_warning.lower() or "critical" in curve_warning.lower():
                severity = Severity.HIGH
            
            warnings.append(WarningItem(
                code="CURVE_WARNING",
                severity=severity,
                title="Curve issue detected",
                detail=curve_warning,
                evidence=[],
                tags=["curve", "mana"]
            ))
    
    return warnings


def rule_synergy_warnings(ctx: WarningContext) -> List[WarningItem]:
    """Import warnings from synergy module"""
    warnings = []
    
    if ctx.synergy_report and hasattr(ctx.synergy_report, 'warnings'):
        for synergy_warning in ctx.synergy_report.warnings:
            warnings.append(WarningItem(
                code="SYNERGY_WARNING",
                severity=Severity.WARN,
                title="Synergy issue detected",
                detail=synergy_warning,
                evidence=[],
                tags=["synergy"]
            ))
    
    return warnings


# ===== DEFAULT RULE SET =====

def default_rules() -> List[WarningRule]:
    """Return the standard set of warning rules"""
    return [
        # Bracket enforcement
        rule_bracket_game_changers,
        rule_bracket_fast_mana_density,
        rule_bracket_tutor_density,
        
        # Mana base
        rule_low_land_count,
        rule_insufficient_ramp,
        rule_too_many_taplands,
        rule_color_intensity,
        
        # Salt/social
        rule_mass_land_destruction,
        rule_extra_turns,
        rule_heavy_stax,
        
        # Combos
        rule_deterministic_combo,
        rule_few_wincons,
        
        # Interaction
        rule_low_interaction,
        rule_no_board_wipes,
        
        # Consistency hazards
        rule_top_heavy_without_ramp,
        rule_low_card_advantage,
        
        # Module integration
        rule_consistency_warnings,
        rule_curve_warnings,
        rule_synergy_warnings,
    ]


# ===== MAIN EVALUATION FUNCTION =====

def evaluate_warnings(
    ctx: WarningContext,
    rules: Optional[List[WarningRule]] = None
) -> WarningsReport:
    """
    Evaluate all warning rules against context.
    
    Args:
        ctx: WarningContext with deck data
        rules: Optional custom rule set (uses defaults if None)
        
    Returns:
        WarningsReport with all detected warnings
    """
    if rules is None:
        rules = default_rules()
    
    items: List[WarningItem] = []
    
    # Run all rules
    for rule in rules:
        items.extend(rule(ctx))
    
    # Deduplicate (same code)
    seen_codes = set()
    unique_items = []
    for item in items:
        if item.code not in seen_codes:
            seen_codes.add(item.code)
            unique_items.append(item)
    
    # Sort by severity (critical first)
    severity_order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.WARN: 2,
        Severity.INFO: 3
    }
    unique_items.sort(key=lambda w: (severity_order[w.severity], w.code))
    
    return WarningsReport(items=unique_items)


# ===== HELPER FUNCTIONS =====

def detect_problematic_cards(
    cards: List[Dict[str, Any]]
) -> Dict[str, List[str]]:
    """
    Detect problematic cards by name and oracle text.
    
    Args:
        cards: List of card dictionaries
        
    Returns:
        Dictionary mapping category to card names
    """
    results = {
        'fast_mana': [],
        'extra_turns': [],
        'mld': [],
        'stax': [],
        'free_counters': [],
        'infinite_combos': [],
        'deterministic_wins': []
    }
    
    for card in cards:
        name = card.get('name', '')
        name_norm = normalize_card_name(name)
        oracle_text = card.get('oracle_text', '').lower()
        
        # Check against known lists
        if name_norm in FAST_MANA_CARDS:
            results['fast_mana'].append(name)
        
        if name_norm in EXTRA_TURN_CARDS:
            results['extra_turns'].append(name)
        elif "take an extra turn" in oracle_text or "extra turn" in oracle_text:
            results['extra_turns'].append(name)
        
        if name_norm in MLD_CARDS:
            results['mld'].append(name)
        elif "destroy all lands" in oracle_text or "destroy all land" in oracle_text:
            results['mld'].append(name)
        
        if name_norm in STAX_CARDS:
            results['stax'].append(name)
        elif any(p in oracle_text for p in ["players can't", "opponents can't", "skip your untap", "can't untap"]):
            results['stax'].append(name)
        
        if name_norm in FREE_INTERACTION_CARDS:
            results['free_counters'].append(name)
        
        if name_norm in INFINITE_COMBO_CARDS:
            results['infinite_combos'].append(name)
        
        if "you win the game" in oracle_text or "each opponent loses the game" in oracle_text:
            results['deterministic_wins'].append(name)
    
    return results


# ===== REPORTING =====

def generate_warnings_summary(report: WarningsReport) -> str:
    """Generate human-readable warnings summary"""
    if not report.items:
        return "No warnings detected - deck looks clean!"
    
    lines = [f"Total Warnings: {len(report.items)}"]
    
    by_severity = report.by_severity()
    
    for severity in [Severity.CRITICAL, Severity.HIGH, Severity.WARN, Severity.INFO]:
        warnings = by_severity.get(severity, [])
        if warnings:
            lines.append(f"\n{severity.value.upper()} ({len(warnings)}):")
            for w in warnings:
                lines.append(f"\n  {w.title}")
                lines.append(f"    {w.detail}")
                if w.evidence:
                    lines.append(f"    Evidence: {', '.join(w.evidence[:5])}")
                    if len(w.evidence) > 5:
                        lines.append(f"    ... and {len(w.evidence) - 5} more")
                if w.suggestion:
                    lines.append(f"    💡 {w.suggestion}")
    
    return "\n".join(lines)

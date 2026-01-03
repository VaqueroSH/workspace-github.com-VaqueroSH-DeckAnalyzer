"""
Format Legality Checker for MTG Decks
"""

import json
import os
from typing import Dict, List, Optional, Any, NamedTuple
from dataclasses import dataclass
from pathlib import Path

from models import Deck
from scryfall_api import ScryfallAPI


class LegalityIssue(NamedTuple):
    """Represents a legality issue found in a deck."""
    severity: str  # 'error', 'warning', 'info'
    category: str  # 'banned', 'restricted', 'construction', 'commander'
    message: str
    card_name: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class LegalityReport:
    """Report of deck legality checking."""
    legal: bool
    format_name: str
    issues: List[LegalityIssue]
    warnings: List[LegalityIssue]
    info: List[LegalityIssue]

    @property
    def all_issues(self) -> List[LegalityIssue]:
        """Get all issues sorted by severity."""
        return (self.issues +
                [issue for issue in self.warnings if issue.severity == 'warning'] +
                [issue for issue in self.info if issue.severity == 'info'])

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        if self.legal:
            return f"✅ Legal in {self.format_name}"

        error_count = len([i for i in self.issues if i.severity == 'error'])
        warning_count = len([i for i in self.warnings if i.severity == 'warning'])

        summary = f"❌ Illegal in {self.format_name}"
        if error_count > 0:
            summary += f" ({error_count} errors"
        if warning_count > 0:
            summary += f", {warning_count} warnings"
        if error_count > 0 or warning_count > 0:
            summary += ")"

        return summary


class FormatChecker:
    """Checks deck legality against format rules."""

    def __init__(self, rules_file: str = None):
        """
        Initialize the format checker.

        Args:
            rules_file: Path to JSON file containing format rules
        """
        if rules_file is None:
            # Default to format_rules.json in the same directory
            current_dir = Path(__file__).parent
            rules_file = current_dir / "format_rules.json"

        self.format_rules = self._load_format_rules(rules_file)
        self.api = ScryfallAPI()

    def _load_format_rules(self, rules_file: str) -> Dict[str, Any]:
        """Load format rules from JSON file."""
        try:
            with open(rules_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Format rules file not found: {rules_file}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in format rules file: {e}")

    def check_deck_legality(self, deck: Deck, format_name: str) -> LegalityReport:
        """
        Check if a deck is legal in the specified format.

        Args:
            deck: The deck to check
            format_name: Name of the format to check against

        Returns:
            LegalityReport with results
        """
        if format_name not in self.format_rules:
            return LegalityReport(
                legal=False,
                format_name=format_name,
                issues=[LegalityIssue(
                    severity='error',
                    category='system',
                    message=f"Unknown format: {format_name}",
                    suggestion="Available formats: " + ", ".join(self.format_rules.keys())
                )],
                warnings=[],
                info=[]
            )

        format_rules = self.format_rules[format_name]
        issues = []
        warnings = []
        info = []

        # Check commander requirements
        commander_issues = self._check_commander_rules(deck, format_rules)
        issues.extend(commander_issues)

        # Check banned cards
        banned_issues = self._check_banned_cards(deck, format_rules)
        issues.extend(banned_issues)

        # Check restricted cards
        restricted_issues = self._check_restricted_cards(deck, format_rules)
        issues.extend(restricted_issues)

        # Check deck construction
        construction_issues = self._check_deck_construction(deck, format_rules)
        issues.extend(construction_issues)

        # Check card legality (if we have set information)
        if deck.card_sets:
            legality_issues = self._check_card_legality(deck, format_rules)
            issues.extend(legality_issues)

        # Generate warnings and info
        warnings.extend(self._generate_warnings(deck, format_rules))
        info.extend(self._generate_info(deck, format_rules))

        return LegalityReport(
            legal=len(issues) == 0,
            format_name=format_name,
            issues=issues,
            warnings=warnings,
            info=info
        )

    def _check_commander_rules(self, deck: Deck, format_rules: Dict[str, Any]) -> List[LegalityIssue]:
        """Check Commander-specific rules."""
        issues = []
        special_rules = format_rules.get('special_rules', {})
        construction = format_rules.get('deck_construction', {})

        if not special_rules.get('commander_required', False):
            return issues

        # Find potential commanders
        commanders = []
        for card_name in deck.cards.keys():
            # Get card info from API to check if it's legendary
            card_info = self.api.get_card(card_name)
            if card_info and 'Legendary' in card_info.type_line:
                commanders.append(card_name)

        # Check commander count
        commander_count = len(commanders)
        required_count = construction.get('commander_count', 1)

        if commander_count == 0:
            issues.append(LegalityIssue(
                severity='error',
                category='commander',
                message="No commander found in deck",
                suggestion="Add a legendary creature as your commander"
            ))
        elif commander_count > required_count:
            issues.append(LegalityIssue(
                severity='error',
                category='commander',
                message=f"Too many commanders: {commander_count} (max: {required_count})",
                suggestion="Remove extra commanders or check partner rules"
            ))
        elif commander_count < required_count:
            issues.append(LegalityIssue(
                severity='error',
                category='commander',
                message=f"Not enough commanders: {commander_count} (required: {required_count})"
            ))

        # Check commander colors (if we have the info)
        if commanders and special_rules.get('commander_colors_determine_identity', False):
            for commander in commanders:
                card_info = self.api.get_card(commander)
                if card_info and card_info.colors:
                    # Commander colors must be in deck colors
                    deck_colors = self._get_deck_colors(deck)
                    missing_colors = set(card_info.colors) - deck_colors
                    if missing_colors:
                        issues.append(LegalityIssue(
                            severity='error',
                            category='commander',
                            message=f"Commander {commander} has colors not in deck: {', '.join(missing_colors)}",
                            suggestion="Add lands or cards of the missing colors"
                        ))

        return issues

    def _check_banned_cards(self, deck: Deck, format_rules: Dict[str, Any]) -> List[LegalityIssue]:
        """Check for banned cards in the deck."""
        issues = []
        banned_cards = format_rules.get('banned_cards', [])

        for card_name, quantity in deck.cards.items():
            if card_name in banned_cards:
                issues.append(LegalityIssue(
                    severity='error',
                    category='banned',
                    message=f"Banned card: {card_name}",
                    card_name=card_name,
                    suggestion="Remove this card from your deck"
                ))

        return issues

    def _check_restricted_cards(self, deck: Deck, format_rules: Dict[str, Any]) -> List[LegalityIssue]:
        """Check for restricted cards (limited to 1 copy)."""
        issues = []
        restricted_cards = format_rules.get('restricted_cards', [])

        for card_name, quantity in deck.cards.items():
            if card_name in restricted_cards and quantity > 1:
                issues.append(LegalityIssue(
                    severity='error',
                    category='restricted',
                    message=f"Restricted card played {quantity} times: {card_name} (max 1)",
                    card_name=card_name,
                    suggestion="Remove extra copies of this card"
                ))

        return issues

    def _check_deck_construction(self, deck: Deck, format_rules: Dict[str, Any]) -> List[LegalityIssue]:
        """Check deck construction rules."""
        issues = []
        construction = format_rules.get('deck_construction', {})

        # Check deck size
        total_cards = sum(deck.cards.values())
        min_size = construction.get('min_deck_size', 60)
        max_size = construction.get('max_deck_size')

        if total_cards < min_size:
            issues.append(LegalityIssue(
                severity='error',
                category='construction',
                message=f"Deck too small: {total_cards} cards (minimum: {min_size})",
                suggestion="Add more cards to reach minimum deck size"
            ))

        if max_size and total_cards > max_size:
            issues.append(LegalityIssue(
                severity='error',
                category='construction',
                message=f"Deck too large: {total_cards} cards (maximum: {max_size})",
                suggestion="Remove cards to meet maximum deck size"
            ))

        # Check maximum copies per card
        max_copies = construction.get('max_copies_per_card', 4)
        for card_name, quantity in deck.cards.items():
            if quantity > max_copies:
                # Skip commanders (they have their own rules)
                card_info = self.api.get_card(card_name)
                if card_info and 'Legendary' not in card_info.type_line:
                    issues.append(LegalityIssue(
                        severity='error',
                        category='construction',
                        message=f"Too many copies: {quantity} of {card_name} (maximum: {max_copies})",
                        card_name=card_name,
                        suggestion="Remove extra copies of this card"
                    ))

        return issues

    def _check_card_legality(self, deck: Deck, format_rules: Dict[str, Any]) -> List[LegalityIssue]:
        """Check if cards are legal in this format (basic implementation)."""
        issues = []
        # This is a placeholder for more advanced legality checking
        # Would need to check printing dates, format legality, etc.
        return issues

    def _generate_warnings(self, deck: Deck, format_rules: Dict[str, Any]) -> List[LegalityIssue]:
        """Generate warnings about potential issues."""
        warnings = []

        # Check for very high land counts
        total_cards = sum(deck.cards.values())
        land_count = 0

        for card_name in deck.cards.keys():
            card_info = self.api.get_card(card_name)
            if card_info and card_info.is_land:
                land_count += deck.cards[card_name]

        land_percentage = (land_count / total_cards * 100) if total_cards > 0 else 0
        if land_percentage > 50:
            warnings.append(LegalityIssue(
                severity='warning',
                category='construction',
                message=f"Very high land count: {land_count} lands ({land_percentage:.1f}%)",
                suggestion="Consider if you need this many lands"
            ))

        return warnings

    def _generate_info(self, deck: Deck, format_rules: Dict[str, Any]) -> List[LegalityIssue]:
        """Generate informational messages."""
        info = []

        # Commander info
        commanders = []
        for card_name in deck.cards.keys():
            card_info = self.api.get_card(card_name)
            if card_info and 'Legendary' in card_info.type_line:
                commanders.append(card_name)

        if commanders:
            info.append(LegalityIssue(
                severity='info',
                category='commander',
                message=f"Commander(s): {', '.join(commanders)}"
            ))

        return info

    def _get_deck_colors(self, deck: Deck) -> set:
        """Get the set of colors in the deck."""
        colors = set()
        for card_name in deck.cards.keys():
            card_info = self.api.get_card(card_name)
            if card_info and card_info.colors:
                colors.update(card_info.colors)
        return colors

    def get_available_formats(self) -> List[str]:
        """Get list of available formats."""
        return list(self.format_rules.keys())

    def get_format_description(self, format_name: str) -> Optional[str]:
        """Get description of a format."""
        if format_name in self.format_rules:
            return self.format_rules[format_name].get('description', '')
        return None

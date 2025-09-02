#!/usr/bin/env python3
"""
Streamlit MTG Deck Analyzer - Web App Version
"""

import streamlit as st
from pathlib import Path
import tempfile
import os

from scryfall_api import ScryfallAPI
from deck_parser import parse_decklist
from models import DeckAnalyzer
from format_checker import FormatChecker

# Page configuration
st.set_page_config(
    page_title="🃏 MTG Deck Analyzer",
    page_icon="🃏",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title and description
st.title("🃏 MTG Deck Analyzer")
st.markdown("### Analyze your Magic: The Gathering decklists with detailed statistics and pricing!")

# Sidebar for options
st.sidebar.header("⚙️ Options")
show_verbose = st.sidebar.checkbox("Show detailed progress", value=False)

# Format legality checker
st.sidebar.header("⚖️ Format Legality")
try:
    format_checker = FormatChecker()
    available_formats = format_checker.get_available_formats()
    selected_format = st.sidebar.selectbox(
        "Check format legality:",
        ["None"] + available_formats,
        help="Check if your deck is legal in selected format"
    )

    if selected_format != "None":
        format_description = format_checker.get_format_description(selected_format)
        if format_description:
            st.sidebar.info(f"📋 {format_description}")
except Exception as e:
    st.sidebar.error(f"❌ Could not load format rules: {e}")
    selected_format = "None"

# Main input area
st.header("📝 Enter Your Decklist")

# Example decklist for users
example_decklist = """1 Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel (FIN) 115
1 Lightning Bolt (M21) 234
1 Demonic Tutor (STA) 90
1 Sol Ring (SLD) 2063
24 Swamp (J25) 89"""

# Text area for decklist input
decklist_text = st.text_area(
    "Paste your decklist here:",
    height=250,
    placeholder="Paste your decklist here...\n\nExample format:\n" + example_decklist,
    help="Supports both formats: '1 Card Name' and '1 Card Name (SET) 123'"
)

# Show example button
if st.button("📋 Use Example Deck"):
    st.rerun()

# File upload option
st.subheader("📁 Or Upload a Decklist File")
uploaded_file = st.file_uploader(
    "Choose a decklist file",
    type=['txt'],
    help="Upload a .txt file with your decklist"
)

# Handle file upload
decklist_content = decklist_text
if uploaded_file is not None:
    decklist_content = uploaded_file.read().decode('utf-8')
    st.success(f"✅ Loaded decklist from: {uploaded_file.name}")
    with st.expander("Preview uploaded content"):
        st.text(decklist_content[:500] + "..." if len(decklist_content) > 500 else decklist_content)

# Analyze button
analyze_button = st.button("🔍 Analyze Deck", type="primary", disabled=not decklist_content.strip())

if analyze_button and decklist_content.strip():
    try:
        # Create a temporary file for parsing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            temp_file.write(decklist_content)
            temp_file_path = temp_file.name
        
        # Progress indicators
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Parse the decklist
            status_text.text("📄 Parsing decklist...")
            progress_bar.progress(20)
            deck = parse_decklist(temp_file_path)
            
            # Initialize API and analyzer
            status_text.text("🌐 Connecting to Scryfall API...")
            progress_bar.progress(40)
            api = ScryfallAPI()
            analyzer = DeckAnalyzer(api)
            
            # Analyze the deck
            status_text.text("🔍 Analyzing deck...")
            progress_bar.progress(60)
            
            # Capture the analysis output if verbose mode is on
            if show_verbose:
                with st.expander("🔧 Detailed Analysis Progress"):
                    stats = analyzer.analyze(deck)
            else:
                # Suppress the print output
                import io
                import sys
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()
                try:
                    stats = analyzer.analyze(deck)
                finally:
                    sys.stdout = old_stdout
            
            progress_bar.progress(100)
            status_text.text("✅ Analysis complete!")
            
            # Display results
            st.success(f"🎉 Successfully analyzed {stats.unique_cards} unique cards!")
            
            # Key metrics in columns
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("💰 Total Value", f"${stats.total_deck_value:.2f}")
            
            with col2:
                st.metric("🃏 Total Cards", f"{stats.total_cards}")
            
            with col3:
                st.metric("🎯 Unique Cards", f"{stats.unique_cards}")
            
            with col4:
                st.metric("⚡ Avg CMC", f"{stats.average_mana_value:.2f}")
            
            # Detailed statistics in expandable sections
            with st.expander("🎨 Color Distribution", expanded=True):
                if stats.color_counts:
                    color_data = []
                    for color_code, count in sorted(stats.color_counts.items()):
                        color_name = stats.color_names.get(color_code, color_code)
                        percentage = (count / stats.unique_cards * 100)
                        color_data.append({"Color": f"{color_name} ({color_code})", "Cards": count, "Percentage": f"{percentage:.1f}%"})
                    st.dataframe(color_data, use_container_width=True)
                else:
                    st.info("Colorless deck")
            
            with st.expander("📈 Mana Curve"):
                if stats.mana_curve:
                    st.write(f"**Average Mana Value:** {stats.average_mana_value:.2f}")
                    
                    # Create mana curve data
                    curve_data = []
                    for mana_value in sorted(stats.mana_curve.keys()):
                        count = stats.mana_curve[mana_value]
                        if mana_value == 0:
                            curve_data.append({"CMC": "0", "Cards": count})
                        elif mana_value >= 7:
                            if mana_value == 7:
                                high_cmc_count = sum(stats.mana_curve.get(i, 0) for i in range(7, 20))
                                curve_data.append({"CMC": "7+", "Cards": high_cmc_count})
                        else:
                            curve_data.append({"CMC": str(mana_value), "Cards": count})
                    
                    st.bar_chart(data=curve_data, x="CMC", y="Cards")
                else:
                    st.info("No nonland cards to analyze")
            
            with st.expander("💎 Most Expensive Cards"):
                if stats.most_expensive_cards:
                    expensive_data = []
                    for card_name, price in stats.most_expensive_cards:
                        expensive_data.append({"Card": card_name, "Price": f"${price:.2f}"})
                    st.dataframe(expensive_data, use_container_width=True)
                else:
                    st.info("Price information not available")
            
            with st.expander("⭐ Rarity Breakdown"):
                if stats.rarity_counts:
                    rarity_data = []
                    rarity_order = ['mythic', 'rare', 'uncommon', 'common', 'special', 'bonus']
                    rarity_names = {
                        'mythic': 'Mythic Rare',
                        'rare': 'Rare', 
                        'uncommon': 'Uncommon',
                        'common': 'Common',
                        'special': 'Special',
                        'bonus': 'Bonus'
                    }
                    
                    for rarity in rarity_order:
                        if rarity in stats.rarity_counts:
                            count = stats.rarity_counts[rarity]
                            percentage = (count / stats.unique_cards * 100)
                            rarity_display = rarity_names.get(rarity, rarity.title())
                            rarity_data.append({"Rarity": rarity_display, "Cards": count, "Percentage": f"{percentage:.1f}%"})
                    
                    st.dataframe(rarity_data, use_container_width=True)
                else:
                    st.info("Rarity information not available")
            
            with st.expander("🎯 Interaction Suite"):
                if stats.interaction_counts:
                    interaction_data = []
                    for interaction_type in ['Removal', 'Tutors', 'Card Draw', 'Ramp', 'Protection']:
                        if interaction_type in stats.interaction_counts:
                            count = stats.interaction_counts[interaction_type]
                            examples = stats.interaction_cards.get(interaction_type, [])[:3]
                            example_str = ", ".join(examples)
                            if len(stats.interaction_cards.get(interaction_type, [])) > 3:
                                example_str += ", ..."
                            interaction_data.append({
                                "Type": interaction_type, 
                                "Count": count,
                                "Examples": example_str
                            })
                    st.dataframe(interaction_data, use_container_width=True)
                else:
                    st.info("No interaction cards identified")
            
            with st.expander("🃏 Card Type Breakdown"):
                if stats.card_types:
                    type_data = []
                    sorted_types = sorted(stats.card_types.items(), key=lambda x: (-x[1], x[0]))
                    
                    for card_type, count in sorted_types:
                        percentage = (count / stats.unique_cards * 100)
                        type_data.append({"Type": card_type, "Cards": count, "Percentage": f"{percentage:.1f}%"})
                    
                    st.dataframe(type_data, use_container_width=True)
                else:
                    st.info("No card type data available")
            
            # Missing cards warning
            if stats.missing_cards:
                with st.expander(f"⚠️ Missing Cards ({len(stats.missing_cards)})", expanded=True):
                    st.warning(f"Could not find information for {len(stats.missing_cards)} cards:")
                    for card in stats.missing_cards:
                        st.write(f"• {card}")
            
            # Success rate
            success_rate = ((stats.unique_cards - len(stats.missing_cards)) / stats.unique_cards * 100) if stats.unique_cards > 0 else 0
            st.info(f"📊 Analysis Success Rate: {success_rate:.1f}%")

            # Format legality check
            if selected_format != "None" and format_checker:
                st.header(f"⚖️ {selected_format} Legality Check")

                try:
                    legality_report = format_checker.check_deck_legality(deck, selected_format)

                    # Show summary
                    if legality_report.legal:
                        st.success(legality_report.get_summary())
                    else:
                        st.error(legality_report.get_summary())

                    # Show detailed issues
                    if legality_report.issues:
                        st.subheader("❌ Issues Found")
                        for issue in legality_report.issues:
                            with st.container():
                                col1, col2 = st.columns([1, 4])
                                with col1:
                                    if issue.severity == 'error':
                                        st.error("🚫")
                                    elif issue.severity == 'warning':
                                        st.warning("⚠️")
                                    else:
                                        st.info("ℹ️")
                                with col2:
                                    st.write(f"**{issue.category.upper()}:** {issue.message}")
                                    if issue.card_name:
                                        st.write(f"*Card:* {issue.card_name}")
                                    if issue.suggestion:
                                        st.write(f"*Suggestion:* {issue.suggestion}")

                    # Show warnings
                    if legality_report.warnings:
                        st.subheader("⚠️ Warnings")
                        for warning in legality_report.warnings:
                            st.warning(f"**{warning.category.upper()}:** {warning.message}")
                            if warning.suggestion:
                                st.write(f"*Suggestion:* {warning.suggestion}")

                    # Show info
                    if legality_report.info:
                        st.subheader("ℹ️ Information")
                        for info in legality_report.info:
                            st.info(f"**{info.category.upper()}:** {info.message}")

                except Exception as e:
                    st.error(f"❌ Error checking legality: {e}")
                    if show_verbose:
                        st.exception(e)

        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
    except Exception as e:
        st.error(f"❌ Error analyzing deck: {e}")
        if show_verbose:
            st.exception(e)

# Footer
st.markdown("---")
st.markdown("### 🎉 Share Your Results!")
st.markdown("Built with ❤️ using [Streamlit](https://streamlit.io) and [Scryfall API](https://scryfall.com/docs/api)")

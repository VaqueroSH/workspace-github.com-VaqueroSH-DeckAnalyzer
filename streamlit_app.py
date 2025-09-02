#!/usr/bin/env python3
"""
Streamlit MTG Deck Analyzer - Web App Version
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import tempfile
import os
import time
from pathlib import Path

from scryfall_api import ScryfallAPI, CardImage
from deck_parser import parse_decklist
from models import DeckAnalyzer
from format_checker import FormatChecker

# Page configuration
st.set_page_config(
    page_title="🃏 MTG Deck Analyzer",
    page_icon="🃏",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize session state
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'landing'
if 'deck_data' not in st.session_state:
    st.session_state.deck_data = None
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None

# Navigation callback functions
def go_to_analysis():
    st.session_state.current_page = 'analysis'

def go_to_landing():
    st.session_state.current_page = 'landing'
    st.session_state.deck_data = None
    st.session_state.analysis_results = None

# Page routing
if st.session_state.current_page == 'landing':
    # ===== LANDING PAGE =====
    # Clean hero section with quick deck upload

    # Hero section
    st.markdown("""
    <div style="text-align: center; padding: 3rem 1rem; background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%); border-radius: 15px; margin-bottom: 2rem; color: white;">
        <h1 style="font-size: 3rem; margin-bottom: 1rem;">🃏 MTG Deck Analyzer</h1>
        <p style="font-size: 1.2rem; margin-bottom: 2rem; opacity: 0.9;">Professional deck analysis with detailed statistics, pricing, and format legality checking</p>
        <div style="display: flex; justify-content: center; gap: 1rem; flex-wrap: wrap;">
            <div style="background: #28a745; padding: 0.5rem 1rem; border-radius: 20px; font-weight: bold;">📊 Advanced Analytics</div>
            <div style="background: #007bff; padding: 0.5rem 1rem; border-radius: 20px; font-weight: bold;">💰 Price Tracking</div>
            <div style="background: #ffc107; padding: 0.5rem 1rem; border-radius: 20px; font-weight: bold;">⚖️ Format Legality</div>
            <div style="background: #dc3545; padding: 0.5rem 1rem; border-radius: 20px; font-weight: bold;">🎯 Interaction Analysis</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Quick upload section
    st.markdown("## 🚀 Quick Start")

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("### 📝 Paste Your Decklist")
        decklist_text = st.text_area(
            "",
            height=200,
            placeholder="""1 Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel (FIN) 115
1 Lightning Bolt (M21) 234
1 Demonic Tutor (STA) 90
1 Sol Ring (SLD) 2063
24 Swamp (J25) 89
24 Mountain (J25) 90""",
            help="Supports both formats: '1 Card Name' and '1 Card Name (SET) 123'",
            label_visibility="collapsed"
        )

        # Example and upload options
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("📋 Use Example Deck", type="secondary"):
                decklist_text = """1 Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel (FIN) 115
1 Lightning Bolt (M21) 234
1 Demonic Tutor (STA) 90
1 Sol Ring (SLD) 2063
24 Swamp (J25) 89
24 Mountain (J25) 90"""
                st.rerun()

        with col_b:
            uploaded_file = st.file_uploader(
                "📁 Upload .txt file",
                type=['txt'],
                help="Upload a decklist file"
            )

        # Handle file upload
        if uploaded_file is not None:
            decklist_text = uploaded_file.read().decode('utf-8')
            st.success(f"✅ Loaded decklist from: {uploaded_file.name}")

        # Analyze button
        if st.button("🔍 Analyze Deck", type="primary", disabled=not decklist_text.strip(), use_container_width=True):
            if decklist_text.strip():
                # Store deck data and navigate to analysis
                st.session_state.deck_data = decklist_text
                st.session_state.current_page = 'analysis'
                st.rerun()

    with col2:
        st.markdown("### ✨ Features")
        st.markdown("""
        - 📊 **Comprehensive Statistics**: Mana curve, color distribution, card types
        - 💰 **Price Analysis**: Total value and most expensive cards
        - ⚖️ **Format Legality**: Check Commander and other format rules
        - 🎯 **Interaction Suite**: Removal, tutors, card draw, ramp analysis
        - 📱 **Mobile Friendly**: Responsive design for all devices
        """)

        st.markdown("### 🎯 Supported Formats")
        st.info("**Commander (EDH)** - Full legality checking with 76+ banned cards")

        # Recent activity placeholder
        st.markdown("### 📈 Sample Results")
        st.metric("Average Analysis Time", "< 30 seconds")
        st.metric("Cards Supported", "25,000+")

elif st.session_state.current_page == 'analysis':
    # ===== ANALYSIS PAGE =====
    # Full dashboard after processing

    # Header with navigation
    col_nav, col_title = st.columns([1, 5])
    with col_nav:
        if st.button("🏠 Home", help="Return to landing page"):
            go_to_landing()
            st.rerun()

    with col_title:
        st.title("🔍 Deck Analysis Dashboard")

    # Get deck data from session
    decklist_content = st.session_state.deck_data

    if not decklist_content:
        st.error("No deck data found. Please return to the landing page.")
        if st.button("🏠 Go to Landing Page"):
            go_to_landing()
            st.rerun()
    else:
        # ===== MAIN ANALYSIS CONTENT =====
        # Add the full analysis dashboard here

        # Initialize sidebar options (only on analysis page)
        st.sidebar.header("⚙️ Analysis Options")
        show_verbose = st.sidebar.checkbox("Show detailed error information", value=False)

        # Format legality checker in sidebar
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

        # ===== COMMANDER BACKGROUND IMAGE =====
        # Try to get commander and set as background
        commander_name = None
        commander_image_url = None

        try:
            # Parse the deck to get commander information
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                temp_file.write(decklist_content)
                temp_file_path = temp_file.name

            deck = parse_decklist(temp_file_path)

            if deck.commander:
                commander_name = deck.commander
                # Try to get commander's image
                api = ScryfallAPI()
                commander_image = api.get_card_image(commander_name, deck.card_sets.get(commander_name))

                if commander_image and commander_image.art_crop:
                    commander_image_url = commander_image.art_crop
                elif commander_image and commander_image.normal:
                    commander_image_url = commander_image.normal
            else:
                # Fallback: Try to identify commander using API
                api = ScryfallAPI()
                potential_commanders = []

                # Look for legendary creatures or planeswalkers with quantity 1
                for card_name, quantity in deck.cards.items():
                    if quantity == 1:  # Commanders are typically single cards
                        try:
                            card_info = api.get_card(card_name, deck.card_sets.get(card_name))
                            if card_info:
                                # Check if it's a legendary creature or planeswalker
                                is_legendary = 'legendary' in card_info.type_line.lower()
                                is_planeswalker = 'planeswalker' in card_info.type_line.lower()

                                if is_legendary or is_planeswalker:
                                    potential_commanders.append((card_name, card_info))
                        except:
                            continue

                # Use the first potential commander found
                if potential_commanders:
                    commander_name, commander_info = potential_commanders[0]
                    commander_image = api.get_card_image(commander_name, deck.card_sets.get(commander_name))

                    if commander_image and commander_image.art_crop:
                        commander_image_url = commander_image.art_crop
                    elif commander_image and commander_image.normal:
                        commander_image_url = commander_image.normal

            # Clean up temp file
            import os
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

        except Exception as e:
            # Silently handle errors - background image is optional
            pass

        # Set commander background if available
        if commander_image_url and commander_name:
            # Create a container with the commander background
            st.markdown(f"""
            <div style="
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                z-index: -1;
                background: linear-gradient(135deg, rgba(0,0,0,0.8) 0%, rgba(20,20,30,0.9) 100%),
                           url('{commander_image_url}') center center / cover no-repeat;
                opacity: 0.1;
                pointer-events: none;
            "></div>
            """, unsafe_allow_html=True)

            # Add commander info overlay
            st.markdown(f"""
            <div style="
                position: fixed;
                top: 80px;
                right: 20px;
                background: rgba(0,0,0,0.8);
                color: white;
                padding: 10px 15px;
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.2);
                font-size: 0.9em;
                z-index: 100;
            ">
                🎯 <strong>Commander:</strong> {commander_name}
            </div>
            """, unsafe_allow_html=True)

        # Full analysis implementation will go here
        st.info("🚧 Analysis dashboard implementation in progress...")

else:
    # Fallback to landing page
    st.session_state.current_page = 'landing'
    st.rerun()
            
    
# Footer
st.markdown("---")
st.markdown("### 🎉 Share Your Results!")
st.markdown("Built with ❤️ using [Streamlit](https://streamlit.io) and [Scryfall API](https://scryfall.com/docs/api)")

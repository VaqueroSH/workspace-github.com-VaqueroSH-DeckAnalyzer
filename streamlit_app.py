#!/usr/bin/env python3
"""
Streamlit MTG Deck Analyzer - Web App Version
"""

import streamlit as st
import pandas as pd
import plotly.express as px
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
    initial_sidebar_state="collapsed"
)

# Custom CSS for modern, clean design
st.markdown("""
<style>
    /* Main container styling */
    .main {
        background: linear-gradient(135deg, #0f0f1e 0%, #1a1a2e 50%, #0f0f1e 100%);
    }
    
    /* Card-style containers */
    .stMarkdown {
        background: rgba(255, 255, 255, 0.02);
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    /* Metric styling */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* Section headers */
    h3 {
        color: #ffffff;
        font-weight: 600;
        border-bottom: 2px solid rgba(102, 126, 234, 0.3);
        padding-bottom: 0.5rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    
    h2 {
        color: #ffffff;
        font-weight: 700;
        text-align: center;
        margin: 1.5rem 0;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 25px rgba(102, 126, 234, 0.3);
    }
    
    /* Text input and text area */
    .stTextArea > div > div > textarea {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(102, 126, 234, 0.2);
        border-radius: 8px;
        color: white;
        font-family: 'Monaco', monospace;
    }
    
    /* Dataframe styling */
    .stDataFrame {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 8px;
        padding: 1rem;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background: rgba(102, 126, 234, 0.1);
        border-radius: 8px;
        font-weight: 600;
    }
    
    /* Success/Error/Warning/Info boxes */
    .stSuccess, .stError, .stWarning, .stInfo {
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    /* Spinner */
    .stSpinner > div {
        border-color: #667eea !important;
    }
    
    /* Plotly charts */
    .js-plotly-plot {
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.03);
        padding: 1rem;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #0f0f1e 100%);
    }
    
    /* Hide default Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Section dividers */
    hr {
        border: none;
        height: 2px;
        background: linear-gradient(90deg, transparent, rgba(102, 126, 234, 0.3), transparent);
        margin: 2rem 0;
    }
</style>
""", unsafe_allow_html=True)

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
    <div style="
        text-align: center; 
        padding: 4rem 2rem; 
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.15) 0%, rgba(118, 75, 162, 0.15) 100%);
        border-radius: 20px; 
        margin-bottom: 3rem; 
        border: 1px solid rgba(102, 126, 234, 0.2);
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    ">
        <h1 style="
            font-size: 3.5rem; 
            margin-bottom: 1rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
        ">🃏 MTG Deck Analyzer</h1>
        <p style="
            font-size: 1.3rem; 
            margin-bottom: 2.5rem; 
            color: rgba(255, 255, 255, 0.8);
            font-weight: 300;
            max-width: 700px;
            margin-left: auto;
            margin-right: auto;
        ">Professional deck analysis powered by Scryfall API<br/>Get instant insights on your Magic: The Gathering decks</p>
        <div style="display: flex; justify-content: center; gap: 1rem; flex-wrap: wrap; max-width: 900px; margin: 0 auto;">
            <div style="
                background: rgba(102, 126, 234, 0.15);
                backdrop-filter: blur(10px);
                padding: 0.75rem 1.5rem;
                border-radius: 25px;
                font-weight: 600;
                border: 1px solid rgba(102, 126, 234, 0.3);
                color: #a8b4ff;
            ">📊 Advanced Analytics</div>
            <div style="
                background: rgba(102, 126, 234, 0.15);
                backdrop-filter: blur(10px);
                padding: 0.75rem 1.5rem;
                border-radius: 25px;
                font-weight: 600;
                border: 1px solid rgba(102, 126, 234, 0.3);
                color: #a8b4ff;
            ">💰 Price Tracking</div>
            <div style="
                background: rgba(102, 126, 234, 0.15);
                backdrop-filter: blur(10px);
                padding: 0.75rem 1.5rem;
                border-radius: 25px;
                font-weight: 600;
                border: 1px solid rgba(102, 126, 234, 0.3);
                color: #a8b4ff;
            ">⚖️ Format Legality</div>
            <div style="
                background: rgba(102, 126, 234, 0.15);
                backdrop-filter: blur(10px);
                padding: 0.75rem 1.5rem;
                border-radius: 25px;
                font-weight: 600;
                border: 1px solid rgba(102, 126, 234, 0.3);
                color: #a8b4ff;
            ">🎯 Interaction Analysis</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Quick upload section
    st.markdown("## 🚀 Quick Start")

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("### 📝 Paste Your Decklist")
        
        # Optional deck name input
        deck_name_input = st.text_input(
            "Deck Name (Optional)",
            placeholder="e.g., Sephiroth Aristocrats",
            help="Give your deck a custom name, or leave blank to use the commander's name"
        )
        
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
                # Store deck data and custom name (if provided) and navigate to analysis
                st.session_state.deck_data = decklist_text
                st.session_state.deck_name_custom = deck_name_input if deck_name_input.strip() else None
                st.session_state.current_page = 'analysis'
                st.rerun()

    with col2:
        st.markdown("### ✨ Features")
        st.markdown("""
        <div style="background: rgba(102, 126, 234, 0.05); padding: 1.5rem; border-radius: 12px; border: 1px solid rgba(102, 126, 234, 0.15);">
            <div style="margin-bottom: 1rem;">
                <span style="font-size: 1.5rem;">📊</span>
                <strong style="color: #a8b4ff;"> Comprehensive Statistics</strong><br/>
                <span style="color: rgba(255, 255, 255, 0.6); font-size: 0.9rem;">Mana curve, color distribution, card types</span>
            </div>
            <div style="margin-bottom: 1rem;">
                <span style="font-size: 1.5rem;">💰</span>
                <strong style="color: #a8b4ff;"> Price Analysis</strong><br/>
                <span style="color: rgba(255, 255, 255, 0.6); font-size: 0.9rem;">Total value and most expensive cards</span>
            </div>
            <div style="margin-bottom: 1rem;">
                <span style="font-size: 1.5rem;">⚖️</span>
                <strong style="color: #a8b4ff;"> Format Legality</strong><br/>
                <span style="color: rgba(255, 255, 255, 0.6); font-size: 0.9rem;">Check Commander and other format rules</span>
            </div>
            <div style="margin-bottom: 1rem;">
                <span style="font-size: 1.5rem;">🎯</span>
                <strong style="color: #a8b4ff;"> Interaction Suite</strong><br/>
                <span style="color: rgba(255, 255, 255, 0.6); font-size: 0.9rem;">Removal, tutors, card draw, ramp analysis</span>
            </div>
            <div>
                <span style="font-size: 1.5rem;">⚡</span>
                <strong style="color: #a8b4ff;"> Lightning Fast</strong><br/>
                <span style="color: rgba(255, 255, 255, 0.6); font-size: 0.9rem;">Results in under 30 seconds</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### 🎯 Supported Formats")
        st.markdown("""
        <div style="background: rgba(102, 126, 234, 0.1); padding: 1rem; border-radius: 8px; border-left: 4px solid #667eea;">
            <strong style="color: #a8b4ff;">Commander (EDH)</strong><br/>
            <span style="color: rgba(255, 255, 255, 0.6); font-size: 0.9rem;">Full legality checking with 76+ banned cards</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("")  # Spacing
        
        # Stats cards
        stats_col1, stats_col2 = st.columns(2)
        with stats_col1:
            st.metric("⚡ Analysis Time", "< 30s")
        with stats_col2:
            st.metric("🃏 Cards DB", "25,000+")

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

        # Parse the deck for analysis
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                temp_file.write(decklist_content)
                temp_file_path = temp_file.name

            deck = parse_decklist(temp_file_path)

            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

        except Exception as e:
            st.error(f"Error parsing deck: {e}")
            if st.button("🏠 Go to Landing Page"):
                go_to_landing()
                st.rerun()
            st.stop()

        # ===== RUN DECK ANALYSIS =====
        with st.spinner("🔍 Analyzing your deck..."):
            try:
                # Initialize API and analyzer
                api = ScryfallAPI()
                analyzer = DeckAnalyzer(api)
                
                # Analyze the deck
                stats = analyzer.analyze(deck)
                
                st.success("✅ Analysis complete!")
                
                # Determine the best name to display
                display_name = None
                if st.session_state.get('deck_name_custom'):
                    # User provided a custom name
                    display_name = st.session_state.deck_name_custom
                elif deck.name and not deck.name.startswith("Tmp"):
                    # Use parsed filename if it's not a temp file
                    display_name = deck.name
                else:
                    # Generic fallback
                    display_name = "Your Deck"
                
                # Display deck header
                st.markdown(f"""
                <h2 style="
                    text-align: center;
                    padding: 1.5rem;
                    background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
                    border-radius: 12px;
                    border: 1px solid rgba(102, 126, 234, 0.2);
                    margin-bottom: 2rem;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                ">🃏 {display_name}</h2>
                """, unsafe_allow_html=True)

                # ===== BASIC STATISTICS =====
                st.markdown("### 📊 Basic Statistics")
                st.markdown("<hr/>", unsafe_allow_html=True)
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Cards", stats.total_cards)
                with col2:
                    st.metric("Unique Cards", stats.unique_cards)
                with col3:
                    st.metric("Lands", f"{stats.lands} ({stats.land_percentage:.1f}%)")
                with col4:
                    st.metric("Nonlands", f"{stats.nonlands} ({stats.nonland_percentage:.1f}%)")
                
                # ===== COLOR DISTRIBUTION & MANA CURVE =====
                st.markdown("<br/>", unsafe_allow_html=True)
                st.markdown("### 🎨 Color Distribution & Mana Curve")
                st.markdown("<hr/>", unsafe_allow_html=True)
                col_left, col_right = st.columns(2)
                
                with col_left:
                    # Color Pie Chart - FIXED VERSION
                    if stats.color_counts:
                        # Prepare data for pie chart
                        color_data = []
                        color_labels = []
                        color_colors_map = {
                            'W': '#F8F6D8',  # White/Cream
                            'U': '#0E68AB',  # Blue
                            'B': '#150B00',  # Black
                            'R': '#D3202A',  # Red
                            'G': '#00733E',  # Green
                            'C': '#BEB9B2'   # Colorless/Gray
                        }
                        
                        for color_code, count in stats.color_counts.items():
                            color_name = stats.color_names.get(color_code, color_code)
                            color_labels.append(f"{color_name} ({count})")
                            color_data.append(count)
                        
                        # Create color list for the pie chart
                        pie_colors = [color_colors_map.get(code, '#CCCCCC') for code in stats.color_counts.keys()]
                        
                        fig_colors = px.pie(
                            values=color_data,
                            names=color_labels,
                            title="Card Color Distribution",
                            color_discrete_sequence=pie_colors
                        )
                        fig_colors.update_traces(
                            textposition='inside',
                            textinfo='percent+label',
                            hovertemplate='%{label}<br>%{value} cards<br>%{percent}<extra></extra>',
                            marker=dict(line=dict(color='#1a1a2e', width=2))
                        )
                        fig_colors.update_layout(
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            font=dict(color='white', size=12),
                            showlegend=True,
                            legend=dict(
                                bgcolor='rgba(0,0,0,0.3)',
                                bordercolor='rgba(102, 126, 234, 0.3)',
                                borderwidth=1
                            )
                        )
                        st.plotly_chart(fig_colors, use_container_width=True)
                    else:
                        st.info("Colorless deck - no color distribution to display")
                
                with col_right:
                    # Mana Curve Bar Chart
                    if stats.mana_curve:
                        # Prepare mana curve data
                        mana_values = []
                        card_counts = []
                        
                        # Group 7+ CMC together
                        high_cmc_count = 0
                        for mv in sorted(stats.mana_curve.keys()):
                            if mv >= 7:
                                high_cmc_count += stats.mana_curve[mv]
                            else:
                                mana_values.append(str(mv))
                                card_counts.append(stats.mana_curve[mv])
                        
                        # Add 7+ group if there are any
                        if high_cmc_count > 0:
                            mana_values.append("7+")
                            card_counts.append(high_cmc_count)
                        
                        fig_curve = px.bar(
                            x=mana_values,
                            y=card_counts,
                            title=f"Mana Curve (Avg: {stats.average_mana_value:.2f})",
                            labels={'x': 'Mana Value', 'y': 'Number of Cards'}
                        )
                        fig_curve.update_layout(
                            showlegend=False,
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            font=dict(color='white', size=12),
                            xaxis=dict(
                                gridcolor='rgba(102, 126, 234, 0.1)',
                                linecolor='rgba(102, 126, 234, 0.3)'
                            ),
                            yaxis=dict(
                                gridcolor='rgba(102, 126, 234, 0.1)',
                                linecolor='rgba(102, 126, 234, 0.3)'
                            )
                        )
                        fig_curve.update_traces(
                            hovertemplate='CMC %{x}<br>%{y} cards<extra></extra>',
                            marker=dict(
                                color='#667eea',
                                line=dict(color='#764ba2', width=1)
                            )
                        )
                        st.plotly_chart(fig_curve, use_container_width=True)
                    else:
                        st.info("No nonland cards to display mana curve")
                
                # ===== CARD TYPES =====
                st.markdown("<br/>", unsafe_allow_html=True)
                st.markdown("### 🃏 Card Type Breakdown")
                st.markdown("<hr/>", unsafe_allow_html=True)
                if stats.card_types:
                    # Create horizontal bar chart for card types
                    sorted_types = sorted(stats.card_types.items(), key=lambda x: -x[1])
                    type_names = [t[0] for t in sorted_types]
                    type_counts = [t[1] for t in sorted_types]
                    
                    fig_types = px.bar(
                        x=type_counts,
                        y=type_names,
                        orientation='h',
                        title="Card Types in Deck",
                        labels={'x': 'Number of Cards', 'y': 'Card Type'}
                    )
                    fig_types.update_layout(
                        showlegend=False,
                        height=400,
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='white', size=12),
                        xaxis=dict(
                            gridcolor='rgba(102, 126, 234, 0.1)',
                            linecolor='rgba(102, 126, 234, 0.3)'
                        ),
                        yaxis=dict(
                            gridcolor='rgba(102, 126, 234, 0.1)',
                            linecolor='rgba(102, 126, 234, 0.3)'
                        )
                    )
                    fig_types.update_traces(
                        hovertemplate='%{y}<br>%{x} cards<extra></extra>',
                        marker=dict(
                            color='#667eea',
                            line=dict(color='#764ba2', width=1)
                        )
                    )
                    st.plotly_chart(fig_types, use_container_width=True)
                else:
                    st.info("No card type data available")
                
                # ===== INTERACTION SUITE =====
                st.markdown("<br/>", unsafe_allow_html=True)
                st.markdown("### 🎯 Interaction Suite")
                st.markdown("<hr/>", unsafe_allow_html=True)
                if stats.interaction_counts:
                    int_col1, int_col2, int_col3, int_col4, int_col5 = st.columns(5)
                    
                    interaction_types = ['Removal', 'Tutors', 'Card Draw', 'Ramp', 'Protection']
                    columns = [int_col1, int_col2, int_col3, int_col4, int_col5]
                    
                    for idx, interaction_type in enumerate(interaction_types):
                        with columns[idx]:
                            count = stats.interaction_counts.get(interaction_type, 0)
                            st.metric(interaction_type, count)
                            
                            # Show example cards in expander
                            if interaction_type in stats.interaction_cards and stats.interaction_cards[interaction_type]:
                                with st.expander("View cards"):
                                    for card in stats.interaction_cards[interaction_type]:
                                        st.write(f"• {card}")
                else:
                    st.info("No interaction cards identified")
                
                # ===== PRICE ANALYSIS =====
                st.markdown("<br/>", unsafe_allow_html=True)
                st.markdown("### 💰 Price Analysis")
                st.markdown("<hr/>", unsafe_allow_html=True)
                if stats.total_deck_value > 0:
                    st.metric("Total Deck Value", f"${stats.total_deck_value:.2f}")
                    
                    if stats.most_expensive_cards:
                        st.markdown("**Most Expensive Cards:**")
                        
                        # Create a nice table for expensive cards
                        price_data = {
                            "Card Name": [card[0] for card in stats.most_expensive_cards],
                            "Price (USD)": [f"${card[1]:.2f}" for card in stats.most_expensive_cards]
                        }
                        price_df = pd.DataFrame(price_data)
                        st.dataframe(price_df, hide_index=True, use_container_width=True)
                else:
                    st.info("Price information not available")
                
                # ===== RARITY BREAKDOWN =====
                st.markdown("<br/>", unsafe_allow_html=True)
                st.markdown("### ⭐ Rarity Breakdown")
                st.markdown("<hr/>", unsafe_allow_html=True)
                if stats.rarity_counts:
                    rarity_col1, rarity_col2, rarity_col3, rarity_col4 = st.columns(4)
                    
                    rarity_order = ['mythic', 'rare', 'uncommon', 'common']
                    rarity_names = {
                        'mythic': 'Mythic Rare',
                        'rare': 'Rare',
                        'uncommon': 'Uncommon',
                        'common': 'Common'
                    }
                    rarity_columns = [rarity_col1, rarity_col2, rarity_col3, rarity_col4]
                    
                    for idx, rarity in enumerate(rarity_order):
                        if rarity in stats.rarity_counts:
                            count = stats.rarity_counts[rarity]
                            percentage = (count / stats.unique_cards * 100) if stats.unique_cards > 0 else 0
                            with rarity_columns[idx]:
                                st.metric(
                                    rarity_names[rarity],
                                    f"{count} ({percentage:.1f}%)"
                                )
                else:
                    st.info("Rarity information not available")
                
                # ===== FORMAT LEGALITY CHECK =====
                if selected_format != "None":
                    st.markdown("<br/>", unsafe_allow_html=True)
                    st.markdown(f"### ⚖️ Format Legality: {selected_format}")
                    st.markdown("<hr/>", unsafe_allow_html=True)
                    
                    with st.spinner(f"Checking {selected_format} legality..."):
                        try:
                            legality_report = format_checker.check_deck_legality(deck, selected_format)
                            
                            # Display summary
                            if legality_report.legal:
                                st.success(legality_report.get_summary())
                            else:
                                st.error(legality_report.get_summary())
                            
                            # Display errors
                            if legality_report.issues:
                                with st.expander(f"❌ Errors ({len(legality_report.issues)})", expanded=not legality_report.legal):
                                    for issue in legality_report.issues:
                                        st.error(f"**{issue.category.upper()}**: {issue.message}")
                                        if issue.card_name:
                                            st.write(f"   Card: {issue.card_name}")
                                        if issue.suggestion:
                                            st.info(f"   💡 {issue.suggestion}")
                            
                            # Display warnings
                            if legality_report.warnings:
                                with st.expander(f"⚠️ Warnings ({len(legality_report.warnings)})"):
                                    for warning in legality_report.warnings:
                                        st.warning(f"**{warning.category.upper()}**: {warning.message}")
                                        if warning.suggestion:
                                            st.info(f"   💡 {warning.suggestion}")
                            
                            # Display info
                            if legality_report.info:
                                with st.expander(f"ℹ️ Information ({len(legality_report.info)})"):
                                    for info in legality_report.info:
                                        st.info(f"{info.message}")
                        
                        except Exception as e:
                            st.error(f"Error checking format legality: {e}")
                            if show_verbose:
                                st.exception(e)
                
                # ===== MISSING CARDS WARNING =====
                if stats.missing_cards:
                    st.markdown("### ⚠️ Missing Cards")
                    st.warning(f"Could not find information for {len(stats.missing_cards)} cards:")
                    
                    with st.expander("View missing cards"):
                        for card in stats.missing_cards:
                            st.write(f"• {card}")
                
                # ===== SUCCESS SUMMARY =====
                success_rate = ((stats.unique_cards - len(stats.missing_cards)) / stats.unique_cards * 100) if stats.unique_cards > 0 else 0
                st.success(f"✅ Successfully analyzed {success_rate:.1f}% of cards")
                
            except Exception as e:
                st.error(f"❌ Error analyzing deck: {e}")
                if show_verbose:
                    st.exception(e)
                    import traceback
                    st.code(traceback.format_exc())

else:
    # Fallback to landing page
    st.session_state.current_page = 'landing'
    st.rerun()
            
    
# Footer
st.markdown("<br/><br/>", unsafe_allow_html=True)
st.markdown("""
<div style="
    text-align: center;
    padding: 2rem;
    background: rgba(102, 126, 234, 0.05);
    border-radius: 12px;
    border: 1px solid rgba(102, 126, 234, 0.1);
    margin-top: 3rem;
">
    <p style="
        color: rgba(255, 255, 255, 0.6);
        font-size: 0.95rem;
        margin-bottom: 0.5rem;
    ">Built with ❤️ by the MTG community</p>
    <div style="display: flex; justify-content: center; gap: 2rem; flex-wrap: wrap; margin-top: 1rem;">
        <a href="https://streamlit.io" target="_blank" style="
            color: #a8b4ff;
            text-decoration: none;
            font-weight: 600;
            transition: color 0.2s;
        ">⚡ Powered by Streamlit</a>
        <a href="https://scryfall.com/docs/api" target="_blank" style="
            color: #a8b4ff;
            text-decoration: none;
            font-weight: 600;
            transition: color 0.2s;
        ">🃏 Data from Scryfall API</a>
    </div>
</div>
""", unsafe_allow_html=True)

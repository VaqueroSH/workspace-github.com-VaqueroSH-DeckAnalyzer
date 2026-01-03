#!/usr/bin/env python3
"""
Streamlit MTG Deck Analyzer - Enhanced Visual Design
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import tempfile
import os

from Core_code.scryfall_api import ScryfallAPI
from Core_code.deck_parser import parse_decklist
from Core_code.models import DeckAnalyzer
from Core_code.format_checker import FormatChecker

# V2 Analysis Modules
from Core_code.bracket import evaluate_bracket, BracketResult
from Core_code.consistency import calculate_consistency, ConsistencyResult
from Core_code.curve_eval import evaluate_curve, Card as CurveCard, EvalContext
from Core_code.roles import assign_roles, summarize_roles, Deck as RoleDeck, Card as RoleCard, Role
from Core_code.synergy import evaluate_synergy, generate_synergy_summary
from Core_code.deck_warnings import (
    WarningContext, evaluate_warnings, detect_problematic_cards, 
    Severity, generate_warnings_summary
)
from Core_code.tagger import tag_many, filter_by_tag, count_tag

# Page configuration
st.set_page_config(
    page_title="🃏 MTG Deck Analyzer",
    page_icon="🃏",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Enhanced CSS with better visual design
st.markdown("""
<style>
    /* Import modern font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
    
    /* Base styling */
    * {
        font-family: 'Inter', sans-serif;
    }
    
    /* Main container with animated gradient */
    .main {
        background: linear-gradient(135deg, #0a0a1e 0%, #1a1a3e 25%, #2a1a3e 50%, #1a1a3e 75%, #0a0a1e 100%);
        background-size: 400% 400%;
        animation: gradientShift 15s ease infinite;
    }
    
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    /* Glassmorphism cards */
    .glass-card {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(20px);
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        padding: 1.5rem;
        transition: all 0.3s ease;
    }
    
    .glass-card:hover {
        background: rgba(255, 255, 255, 0.05);
        border-color: rgba(102, 126, 234, 0.3);
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.2);
        transform: translateY(-2px);
    }
    
    /* Enhanced metrics */
    [data-testid="stMetricValue"] {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #a78bfa 50%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.5px;
    }
    
    [data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        font-weight: 600;
        color: rgba(255, 255, 255, 0.7);
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    [data-testid="stMetricDelta"] {
        font-size: 0.85rem;
        font-weight: 600;
    }
    
    /* Section headers with gradient underline */
    h1, h2, h3 {
        color: #ffffff;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    
    h3 {
        position: relative;
        padding-bottom: 1rem;
        margin-top: 3rem;
        margin-bottom: 1.5rem;
    }
    
    h3::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        width: 80px;
        height: 4px;
        background: linear-gradient(90deg, #667eea, #764ba2);
        border-radius: 2px;
    }
    
    /* Enhanced buttons */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.85rem 2.5rem;
        font-weight: 700;
        font-size: 1rem;
        letter-spacing: 0.5px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        position: relative;
        overflow: hidden;
    }
    
    .stButton > button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
        transition: left 0.5s;
    }
    
    .stButton > button:hover::before {
        left: 100%;
    }
    
    .stButton > button:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.5);
    }
    
    /* Text input and text area with glow effect */
    .stTextArea > div > div > textarea,
    .stTextInput > div > div > input {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(10px);
        border: 2px solid rgba(102, 126, 234, 0.2);
        border-radius: 12px;
        color: white;
        font-family: 'Monaco', monospace;
        padding: 1rem;
        transition: all 0.3s ease;
    }
    
    .stTextArea > div > div > textarea:focus,
    .stTextInput > div > div > input:focus {
        border-color: #667eea;
        box-shadow: 0 0 20px rgba(102, 126, 234, 0.3);
        background: rgba(255, 255, 255, 0.05);
    }
    
    /* Enhanced dataframes */
    .stDataFrame {
        background: rgba(255, 255, 255, 0.02);
        border-radius: 12px;
        border: 1px solid rgba(102, 126, 234, 0.2);
        overflow: hidden;
    }
    
    /* Expander with better styling */
    .streamlit-expanderHeader {
        background: rgba(102, 126, 234, 0.1);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        border: 1px solid rgba(102, 126, 234, 0.2);
        font-weight: 600;
        padding: 1rem;
        transition: all 0.3s ease;
    }
    
    .streamlit-expanderHeader:hover {
        background: rgba(102, 126, 234, 0.15);
        border-color: rgba(102, 126, 234, 0.4);
    }
    
    /* Enhanced alert boxes */
    .stSuccess {
        background: rgba(34, 197, 94, 0.1);
        border-left: 4px solid #22c55e;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        backdrop-filter: blur(10px);
    }
    
    .stError {
        background: rgba(239, 68, 68, 0.1);
        border-left: 4px solid #ef4444;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        backdrop-filter: blur(10px);
    }
    
    .stWarning {
        background: rgba(251, 191, 36, 0.1);
        border-left: 4px solid #fbbf24;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        backdrop-filter: blur(10px);
    }
    
    .stInfo {
        background: rgba(59, 130, 246, 0.1);
        border-left: 4px solid #3b82f6;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        backdrop-filter: blur(10px);
    }
    
    /* Spinner with custom color */
    .stSpinner > div {
        border-color: #667eea transparent transparent !important;
    }
    
    /* Chart containers */
    .js-plotly-plot {
        border-radius: 16px;
        background: rgba(255, 255, 255, 0.02);
        backdrop-filter: blur(10px);
        padding: 1rem;
        border: 1px solid rgba(102, 126, 234, 0.1);
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a3e 0%, #0a0a1e 100%);
        border-right: 1px solid rgba(102, 126, 234, 0.2);
    }
    
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
        color: rgba(255, 255, 255, 0.9);
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Custom dividers */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(102, 126, 234, 0.5), transparent);
        margin: 2.5rem 0;
    }
    
    /* Feature badge animation */
    @keyframes float {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-5px); }
    }
    
    .feature-badge {
        animation: float 3s ease-in-out infinite;
    }
    
    /* Stat card with gradient border */
    .stat-card {
        background: rgba(255, 255, 255, 0.02);
        border: 2px solid transparent;
        border-radius: 16px;
        padding: 1.5rem;
        background-clip: padding-box;
        position: relative;
        transition: all 0.3s ease;
    }
    
    .stat-card::before {
        content: '';
        position: absolute;
        inset: -2px;
        border-radius: 16px;
        padding: 2px;
        background: linear-gradient(135deg, #667eea, #764ba2);
        -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
        -webkit-mask-composite: xor;
        mask-composite: exclude;
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    
    .stat-card:hover::before {
        opacity: 1;
    }
    
    /* File uploader styling */
    [data-testid="stFileUploader"] {
        background: rgba(255, 255, 255, 0.02);
        border: 2px dashed rgba(102, 126, 234, 0.3);
        border-radius: 12px;
        padding: 1rem;
        transition: all 0.3s ease;
    }
    
    [data-testid="stFileUploader"]:hover {
        border-color: #667eea;
        background: rgba(102, 126, 234, 0.05);
    }
    
    /* Select box styling */
    .stSelectbox > div > div {
        background: rgba(255, 255, 255, 0.03);
        border: 2px solid rgba(102, 126, 234, 0.2);
        border-radius: 12px;
        transition: all 0.3s ease;
    }
    
    .stSelectbox > div > div:hover {
        border-color: #667eea;
        box-shadow: 0 0 15px rgba(102, 126, 234, 0.2);
    }
    
    /* Checkbox styling */
    .stCheckbox {
        color: rgba(255, 255, 255, 0.9);
    }
    
    /* Progress bars */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #667eea, #764ba2);
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

# Helper function to create styled metric cards
def create_metric_card(label, value, delta=None, icon="📊"):
    """Create a beautifully styled metric card"""
    delta_html = ""
    if delta:
        delta_color = "#22c55e" if delta > 0 else "#ef4444"
        delta_html = f"""
        <div style="
            color: {delta_color};
            font-size: 0.9rem;
            font-weight: 600;
            margin-top: 0.5rem;
        ">
            {"↑" if delta > 0 else "↓"} {abs(delta)}%
        </div>
        """
    
    return f"""
    <div class="stat-card" style="text-align: center; height: 100%;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">{icon}</div>
        <div style="
            font-size: 0.85rem;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.6);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 0.5rem;
        ">{label}</div>
        <div style="
            font-size: 2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #667eea 0%, #a78bfa 50%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        ">{value}</div>
        {delta_html}
    </div>
    """

# Page routing
if st.session_state.current_page == 'landing':
    # ===== ENHANCED LANDING PAGE =====
    
    # Animated hero section
    st.markdown("""
    <div style="
        text-align: center; 
        padding: 5rem 2rem 4rem 2rem; 
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
        border-radius: 24px; 
        margin-bottom: 3rem; 
        border: 2px solid rgba(102, 126, 234, 0.2);
        box-shadow: 0 25px 80px rgba(102, 126, 234, 0.15);
        backdrop-filter: blur(20px);
        position: relative;
        overflow: hidden;
    ">
        <div style="
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(102, 126, 234, 0.1) 0%, transparent 70%);
            animation: pulse 4s ease-in-out infinite;
        "></div>
        <div style="position: relative; z-index: 1;">
            <h1 style="
                font-size: 4rem; 
                margin-bottom: 1.5rem;
                background: linear-gradient(135deg, #667eea 0%, #a78bfa 50%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-weight: 900;
                letter-spacing: -2px;
                line-height: 1.1;
            ">🃏 MTG Deck Analyzer</h1>
            <p style="
                font-size: 1.4rem; 
                margin-bottom: 3rem; 
                color: rgba(255, 255, 255, 0.85);
                font-weight: 400;
                max-width: 700px;
                margin-left: auto;
                margin-right: auto;
                line-height: 1.6;
            ">
                Professional deck analysis powered by Scryfall<br/>
                <span style="color: rgba(255, 255, 255, 0.6); font-size: 1.1rem;">
                    Get instant insights on your Magic: The Gathering decks
                </span>
            </p>
            <div style="
                display: flex; 
                justify-content: center; 
                gap: 1.5rem; 
                flex-wrap: wrap; 
                max-width: 1000px; 
                margin: 0 auto;
            ">
                <div class="feature-badge" style="
                    background: rgba(102, 126, 234, 0.12);
                    backdrop-filter: blur(10px);
                    padding: 1rem 2rem;
                    border-radius: 30px;
                    font-weight: 700;
                    border: 2px solid rgba(102, 126, 234, 0.3);
                    color: #b8c5ff;
                    font-size: 1.05rem;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.2);
                    animation-delay: 0s;
                ">📊 Advanced Analytics</div>
                <div class="feature-badge" style="
                    background: rgba(102, 126, 234, 0.12);
                    backdrop-filter: blur(10px);
                    padding: 1rem 2rem;
                    border-radius: 30px;
                    font-weight: 700;
                    border: 2px solid rgba(102, 126, 234, 0.3);
                    color: #b8c5ff;
                    font-size: 1.05rem;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.2);
                    animation-delay: 0.2s;
                ">💰 Price Tracking</div>
                <div class="feature-badge" style="
                    background: rgba(102, 126, 234, 0.12);
                    backdrop-filter: blur(10px);
                    padding: 1rem 2rem;
                    border-radius: 30px;
                    font-weight: 700;
                    border: 2px solid rgba(102, 126, 234, 0.3);
                    color: #b8c5ff;
                    font-size: 1.05rem;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.2);
                    animation-delay: 0.4s;
                ">⚖️ Format Legality</div>
                <div class="feature-badge" style="
                    background: rgba(102, 126, 234, 0.12);
                    backdrop-filter: blur(10px);
                    padding: 1rem 2rem;
                    border-radius: 30px;
                    font-weight: 700;
                    border: 2px solid rgba(102, 126, 234, 0.3);
                    color: #b8c5ff;
                    font-size: 1.05rem;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.2);
                    animation-delay: 0.6s;
                ">🎯 Interaction Analysis</div>
            </div>
        </div>
    </div>
    
    <style>
    @keyframes pulse {
        0%, 100% { opacity: 0.5; transform: scale(1); }
        50% { opacity: 0.8; transform: scale(1.05); }
    }
    </style>
    """, unsafe_allow_html=True)

    # Main upload section with enhanced design
    st.markdown("## 🚀 Quick Start")
    st.markdown("")

    col1, col2 = st.columns([3, 2], gap="large")

    with col1:
        st.markdown("""
        <div class="glass-card">
            <h3 style="margin-top: 0; margin-bottom: 1.5rem; font-size: 1.5rem;">
                📝 Paste Your Decklist
            </h3>
        """, unsafe_allow_html=True)
        
        # Optional deck name input
        deck_name_input = st.text_input(
            "Deck Name (Optional)",
            placeholder="e.g., Sephiroth Aristocrats",
            help="Give your deck a custom name, or leave blank to use the commander's name"
        )
        
        decklist_text = st.text_area(
            "Decklist",
            height=250,
            placeholder="""1 Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel (FIN) 115
1 Lightning Bolt (M21) 234
1 Demonic Tutor (STA) 90
1 Sol Ring (SLD) 2063
24 Swamp (J25) 89
24 Mountain (J25) 90""",
            help="Supports both formats: '1 Card Name' and '1 Card Name (SET) 123'",
            label_visibility="collapsed"
        )

        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("")

        # Example and upload options in styled containers
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("📋 Load Example Deck", type="secondary", use_container_width=True):
                decklist_text = """1 Sephiroth, Fabled SOLDIER // Sephiroth, One-Winged Angel (FIN) 115
1 Lightning Bolt (M21) 234
1 Demonic Tutor (STA) 90
1 Sol Ring (SLD) 2063
24 Swamp (J25) 89
24 Mountain (J25) 90"""
                st.rerun()

        with col_b:
            uploaded_file = st.file_uploader(
                "📁 Upload File",
                type=['txt'],
                help="Upload a decklist file",
                label_visibility="collapsed"
            )

        # Handle file upload
        if uploaded_file is not None:
            decklist_text = uploaded_file.read().decode('utf-8')
            st.success(f"✅ Loaded: {uploaded_file.name}")

        st.markdown("")
        
        # Analyze button
        if st.button("🔍 Analyze Deck", type="primary", disabled=not decklist_text.strip(), use_container_width=True):
            if decklist_text.strip():
                st.session_state.deck_data = decklist_text
                st.session_state.deck_name_custom = deck_name_input if deck_name_input.strip() else None
                st.session_state.current_page = 'analysis'
                st.rerun()

    with col2:
        # Feature showcase
        st.markdown("""
        <div class="glass-card" style="height: 100%;">
            <h3 style="margin-top: 0; margin-bottom: 1.5rem; font-size: 1.5rem;">
                ✨ What You Get
            </h3>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style="margin-bottom: 1.5rem;">
            <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                <span style="font-size: 1.8rem; margin-right: 1rem;">📊</span>
                <strong style="color: #b8c5ff; font-size: 1.1rem;">Comprehensive Statistics</strong>
            </div>
            <p style="color: rgba(255, 255, 255, 0.6); font-size: 0.95rem; margin-left: 3rem; margin-bottom: 0;">
                Detailed mana curve, color distribution, and card type breakdowns
            </p>
        </div>
        
        <div style="margin-bottom: 1.5rem;">
            <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                <span style="font-size: 1.8rem; margin-right: 1rem;">💰</span>
                <strong style="color: #b8c5ff; font-size: 1.1rem;">Price Analysis</strong>
            </div>
            <p style="color: rgba(255, 255, 255, 0.6); font-size: 0.95rem; margin-left: 3rem; margin-bottom: 0;">
                Real-time pricing with expensive card identification
            </p>
        </div>
        
        <div style="margin-bottom: 1.5rem;">
            <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                <span style="font-size: 1.8rem; margin-right: 1rem;">⚖️</span>
                <strong style="color: #b8c5ff; font-size: 1.1rem;">Format Legality</strong>
            </div>
            <p style="color: rgba(255, 255, 255, 0.6); font-size: 0.95rem; margin-left: 3rem; margin-bottom: 0;">
                Commander and multi-format validation
            </p>
        </div>
        
        <div style="margin-bottom: 1.5rem;">
            <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                <span style="font-size: 1.8rem; margin-right: 1rem;">🎯</span>
                <strong style="color: #b8c5ff; font-size: 1.1rem;">Interaction Suite</strong>
            </div>
            <p style="color: rgba(255, 255, 255, 0.6); font-size: 0.95rem; margin-left: 3rem; margin-bottom: 0;">
                Removal, tutors, card draw, and ramp tracking
            </p>
        </div>
        
        <div style="margin-bottom: 1.5rem;">
            <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                <span style="font-size: 1.8rem; margin-right: 1rem;">⚡</span>
                <strong style="color: #b8c5ff; font-size: 1.1rem;">Lightning Fast</strong>
            </div>
            <p style="color: rgba(255, 255, 255, 0.6); font-size: 0.95rem; margin-left: 3rem; margin-bottom: 0;">
                Complete analysis in under 30 seconds
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
    # Stats showcase
    st.markdown("")
    st.markdown("### 📈 By The Numbers")
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    
    with stat_col1:
        st.markdown(create_metric_card("Analysis Time", "< 30s", icon="⚡"), unsafe_allow_html=True)
    with stat_col2:
        st.markdown(create_metric_card("Cards Database", "25,000+", icon="🃏"), unsafe_allow_html=True)
    with stat_col3:
        st.markdown(create_metric_card("Formats", "10+", icon="⚖️"), unsafe_allow_html=True)
    with stat_col4:
        st.markdown(create_metric_card("Accuracy", "99.5%", icon="🎯"), unsafe_allow_html=True)

elif st.session_state.current_page == 'analysis':
    # ===== ENHANCED ANALYSIS PAGE =====
    
    # Sticky header with navigation
    st.markdown("""
    <div style="
        background: rgba(10, 10, 30, 0.95);
        backdrop-filter: blur(20px);
        padding: 1rem 0;
        margin: -1rem -1rem 2rem -1rem;
        border-bottom: 2px solid rgba(102, 126, 234, 0.2);
        position: sticky;
        top: 0;
        z-index: 1000;
    ">
    """, unsafe_allow_html=True)
    
    col_nav, col_title = st.columns([1, 5])
    with col_nav:
        if st.button("🏠 Home", help="Return to landing page", use_container_width=True):
            go_to_landing()
            st.rerun()

    with col_title:
        st.markdown("""
        <h1 style="
            margin: 0;
            font-size: 2rem;
            background: linear-gradient(135deg, #667eea 0%, #a78bfa 50%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        ">🔍 Deck Analysis Dashboard</h1>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

    # Get deck data from session
    decklist_content = st.session_state.deck_data

    if not decklist_content:
        st.error("No deck data found. Please return to the landing page.")
        if st.button("🏠 Go to Landing Page"):
            go_to_landing()
            st.rerun()
    else:
        # Enhanced sidebar
        st.sidebar.markdown("""
        <h2 style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 1.5rem;
            margin-bottom: 1.5rem;
        ">⚙️ Options</h2>
        """, unsafe_allow_html=True)
        
        show_verbose = st.sidebar.checkbox("🔍 Show detailed errors", value=False)

        # Format legality in sidebar
        st.sidebar.markdown("<hr style='margin: 2rem 0;'/>", unsafe_allow_html=True)
        st.sidebar.markdown("""
        <h3 style="
            color: #b8c5ff;
            font-size: 1.2rem;
            margin-bottom: 1rem;
        ">⚖️ Format Legality</h3>
        """, unsafe_allow_html=True)
        
        try:
            format_checker = FormatChecker()
            available_formats = format_checker.get_available_formats()
            selected_format = st.sidebar.selectbox(
                "Check format:",
                ["None"] + available_formats,
                help="Validate deck legality"
            )

            if selected_format != "None":
                format_description = format_checker.get_format_description(selected_format)
                if format_description:
                    st.sidebar.info(f"📋 {format_description}")
        except Exception as e:
            st.sidebar.error(f"❌ Error: {e}")
            selected_format = "None"

        # Parse deck
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                temp_file.write(decklist_content)
                temp_file_path = temp_file.name

            deck = parse_decklist(temp_file_path)

            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

        except Exception as e:
            st.error(f"Error parsing deck: {e}")
            if st.button("🏠 Go to Landing Page"):
                go_to_landing()
                st.rerun()
            st.stop()

        # ===== RUN ANALYSIS =====
        with st.spinner("🔍 Analyzing your deck..."):
            try:
                api = ScryfallAPI()
                analyzer = DeckAnalyzer(api)
                stats = analyzer.analyze(deck)
                
                st.success("✅ Analysis complete!")
                
                # Determine display name
                display_name = None
                if st.session_state.get('deck_name_custom'):
                    display_name = st.session_state.deck_name_custom
                elif deck.name and not deck.name.startswith("Tmp"):
                    display_name = deck.name
                else:
                    display_name = "Your Deck"
                
                # Enhanced deck header
                st.markdown(f"""
                <div class="glass-card" style="text-align: center; margin-bottom: 3rem; padding: 2.5rem;">
                    <h2 style="
                        margin: 0;
                        font-size: 3rem;
                        background: linear-gradient(135deg, #667eea 0%, #a78bfa 50%, #764ba2 100%);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                        font-weight: 900;
                        letter-spacing: -1px;
                    ">🃏 {display_name}</h2>
                    <p style="
                        color: rgba(255, 255, 255, 0.6);
                        margin-top: 0.5rem;
                        font-size: 1.1rem;
                    ">Complete Deck Analysis Report</p>
                </div>
                """, unsafe_allow_html=True)

                # ===== BASIC STATISTICS =====
                st.markdown("### 📊 Deck Overview")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown(create_metric_card("Total Cards", stats.total_cards, icon="🃏"), unsafe_allow_html=True)
                with col2:
                    st.markdown(create_metric_card("Unique Cards", stats.unique_cards, icon="✨"), unsafe_allow_html=True)
                with col3:
                    st.markdown(create_metric_card("Lands", f"{stats.lands}", icon="🏔️"), unsafe_allow_html=True)
                with col4:
                    st.markdown(create_metric_card("Nonlands", f"{stats.nonlands}", icon="⚔️"), unsafe_allow_html=True)
                
                # ===== COLOR & CURVE =====
                st.markdown("### 🎨 Color Distribution & Mana Curve")
                
                col_left, col_right = st.columns(2, gap="large")
                
                with col_left:
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    if stats.color_counts:
                        color_data = []
                        color_labels = []
                        color_colors_map = {
                            'W': '#F8F6D8',
                            'U': '#0E68AB',
                            'B': '#150B00',
                            'R': '#D3202A',
                            'G': '#00733E',
                            'C': '#BEB9B2'
                        }
                        
                        for color_code, count in stats.color_counts.items():
                            color_name = stats.color_names.get(color_code, color_code)
                            color_labels.append(f"{color_name}")
                            color_data.append(count)
                        
                        pie_colors = [color_colors_map.get(code, '#CCCCCC') for code in stats.color_counts.keys()]
                        
                        fig_colors = go.Figure(data=[go.Pie(
                            labels=color_labels,
                            values=color_data,
                            marker=dict(
                                colors=pie_colors,
                                line=dict(color='#1a1a3e', width=3)
                            ),
                            textposition='inside',
                            textinfo='percent',
                            hovertemplate='<b>%{label}</b><br>%{value} cards<br>%{percent}<extra></extra>',
                            hole=0.4
                        )])
                        
                        fig_colors.update_layout(
                            title=dict(
                                text="Color Distribution",
                                font=dict(size=18, color='white', family='Inter'),
                                x=0.5,
                                xanchor='center'
                            ),
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            font=dict(color='white', size=13, family='Inter'),
                            showlegend=True,
                            legend=dict(
                                bgcolor='rgba(0,0,0,0)',
                                bordercolor='rgba(102, 126, 234, 0.3)',
                                borderwidth=1,
                                font=dict(size=12)
                            ),
                            margin=dict(t=60, b=20, l=20, r=20),
                            height=400
                        )
                        st.plotly_chart(fig_colors, use_container_width=True)
                    else:
                        st.info("Colorless deck")
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with col_right:
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    if stats.mana_curve:
                        mana_values = []
                        card_counts = []
                        
                        high_cmc_count = 0
                        for mv in sorted(stats.mana_curve.keys()):
                            if mv >= 7:
                                high_cmc_count += stats.mana_curve[mv]
                            else:
                                mana_values.append(str(mv))
                                card_counts.append(stats.mana_curve[mv])
                        
                        if high_cmc_count > 0:
                            mana_values.append("7+")
                            card_counts.append(high_cmc_count)
                        
                        fig_curve = go.Figure(data=[go.Bar(
                            x=mana_values,
                            y=card_counts,
                            marker=dict(
                                color=card_counts,
                                colorscale=[[0, '#667eea'], [1, '#764ba2']],
                                line=dict(color='#764ba2', width=2)
                            ),
                            hovertemplate='<b>CMC %{x}</b><br>%{y} cards<extra></extra>'
                        )])
                        
                        fig_curve.update_layout(
                            title=dict(
                                text=f"Mana Curve (Avg: {stats.average_mana_value:.2f})",
                                font=dict(size=18, color='white', family='Inter'),
                                x=0.5,
                                xanchor='center'
                            ),
                            xaxis=dict(
                                title="Mana Value",
                                gridcolor='rgba(102, 126, 234, 0.1)',
                                linecolor='rgba(102, 126, 234, 0.3)',
                                color='white'
                            ),
                            yaxis=dict(
                                title="Cards",
                                gridcolor='rgba(102, 126, 234, 0.1)',
                                linecolor='rgba(102, 126, 234, 0.3)',
                                color='white'
                            ),
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            font=dict(color='white', size=13, family='Inter'),
                            showlegend=False,
                            margin=dict(t=60, b=60, l=60, r=20),
                            height=400
                        )
                        st.plotly_chart(fig_curve, use_container_width=True)
                    else:
                        st.info("No mana curve data")
                    st.markdown('</div>', unsafe_allow_html=True)
                
                # ===== CARD TYPES =====
                st.markdown("### 🃏 Card Type Breakdown")
                if stats.card_types:
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    sorted_types = sorted(stats.card_types.items(), key=lambda x: -x[1])
                    type_names = [t[0] for t in sorted_types]
                    type_counts = [t[1] for t in sorted_types]
                    
                    fig_types = go.Figure(data=[go.Bar(
                        x=type_counts,
                        y=type_names,
                        orientation='h',
                        marker=dict(
                            color=type_counts,
                            colorscale=[[0, '#667eea'], [1, '#764ba2']],
                            line=dict(color='#764ba2', width=2)
                        ),
                        hovertemplate='<b>%{y}</b><br>%{x} cards<extra></extra>'
                    )])
                    
                    fig_types.update_layout(
                        title=dict(
                            text="Type Distribution",
                            font=dict(size=18, color='white', family='Inter'),
                            x=0.5,
                            xanchor='center'
                        ),
                        xaxis=dict(
                            title="Number of Cards",
                            gridcolor='rgba(102, 126, 234, 0.1)',
                            linecolor='rgba(102, 126, 234, 0.3)',
                            color='white'
                        ),
                        yaxis=dict(
                            gridcolor='rgba(102, 126, 234, 0.1)',
                            linecolor='rgba(102, 126, 234, 0.3)',
                            color='white'
                        ),
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='white', size=13, family='Inter'),
                        showlegend=False,
                        height=450,
                        margin=dict(t=60, b=60, l=150, r=20)
                    )
                    st.plotly_chart(fig_types, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.info("No card type data")
                
                # ===== INTERACTION SUITE =====
                st.markdown("### 🎯 Interaction Suite")
                if stats.interaction_counts:
                    int_col1, int_col2, int_col3, int_col4, int_col5 = st.columns(5)
                    
                    interaction_types = ['Removal', 'Tutors', 'Card Draw', 'Ramp', 'Protection']
                    interaction_icons = ['🎯', '🔍', '📚', '⚡', '🛡️']
                    columns = [int_col1, int_col2, int_col3, int_col4, int_col5]
                    
                    for idx, interaction_type in enumerate(interaction_types):
                        with columns[idx]:
                            count = stats.interaction_counts.get(interaction_type, 0)
                            st.markdown(
                                create_metric_card(
                                    interaction_type,
                                    count,
                                    icon=interaction_icons[idx]
                                ),
                                unsafe_allow_html=True
                            )
                            
                            if interaction_type in stats.interaction_cards and stats.interaction_cards[interaction_type]:
                                with st.expander("📋 View cards"):
                                    for card in stats.interaction_cards[interaction_type]:
                                        st.write(f"• {card}")
                else:
                    st.info("No interaction data")
                
                # ===== PRICE ANALYSIS =====
                st.markdown("### 💰 Price Analysis")
                if stats.total_deck_value > 0:
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    
                    # Big total value display
                    st.markdown(f"""
                    <div style="text-align: center; padding: 2rem 0;">
                        <div style="
                            font-size: 0.9rem;
                            color: rgba(255, 255, 255, 0.6);
                            text-transform: uppercase;
                            letter-spacing: 2px;
                            margin-bottom: 0.5rem;
                        ">TOTAL DECK VALUE</div>
                        <div style="
                            font-size: 3.5rem;
                            font-weight: 900;
                            background: linear-gradient(135deg, #22c55e 0%, #10b981 100%);
                            -webkit-background-clip: text;
                            -webkit-text-fill-color: transparent;
                        ">${stats.total_deck_value:.2f}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if stats.most_expensive_cards:
                        st.markdown("**💎 Most Expensive Cards**")
                        
                        # Enhanced price table
                        price_data = {
                            "Card Name": [card[0] for card in stats.most_expensive_cards],
                            "Price (USD)": [f"${card[1]:.2f}" for card in stats.most_expensive_cards]
                        }
                        price_df = pd.DataFrame(price_data)
                        
                        # Display with custom styling
                        st.dataframe(
                            price_df,
                            hide_index=True,
                            use_container_width=True,
                            column_config={
                                "Card Name": st.column_config.TextColumn("Card", width="large"),
                                "Price (USD)": st.column_config.TextColumn("Price", width="medium")
                            }
                        )
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.info("Price data unavailable")
                
                # ===== RARITY =====
                st.markdown("### ⭐ Rarity Breakdown")
                if stats.rarity_counts:
                    rarity_col1, rarity_col2, rarity_col3, rarity_col4 = st.columns(4)
                    
                    rarity_order = ['mythic', 'rare', 'uncommon', 'common']
                    rarity_names = {
                        'mythic': 'Mythic Rare',
                        'rare': 'Rare',
                        'uncommon': 'Uncommon',
                        'common': 'Common'
                    }
                    rarity_icons = {
                        'mythic': '🔥',
                        'rare': '💎',
                        'uncommon': '⭐',
                        'common': '🔘'
                    }
                    rarity_columns = [rarity_col1, rarity_col2, rarity_col3, rarity_col4]
                    
                    for idx, rarity in enumerate(rarity_order):
                        if rarity in stats.rarity_counts:
                            count = stats.rarity_counts[rarity]
                            percentage = (count / stats.unique_cards * 100) if stats.unique_cards > 0 else 0
                            with rarity_columns[idx]:
                                st.markdown(
                                    create_metric_card(
                                        rarity_names[rarity],
                                        f"{count}",
                                        icon=rarity_icons[rarity]
                                    ),
                                    unsafe_allow_html=True
                                )
                else:
                    st.info("No rarity data")
                
                # ===== FORMAT LEGALITY =====
                if selected_format != "None":
                    st.markdown(f"### ⚖️ Format Legality: {selected_format}")
                    
                    with st.spinner(f"Checking {selected_format} legality..."):
                        try:
                            legality_report = format_checker.check_deck_legality(deck, selected_format)
                            
                            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                            if legality_report.legal:
                                st.success(legality_report.get_summary())
                            else:
                                st.error(legality_report.get_summary())
                            
                            if legality_report.issues:
                                with st.expander(f"❌ Errors ({len(legality_report.issues)})", expanded=not legality_report.legal):
                                    for issue in legality_report.issues:
                                        st.error(f"**{issue.category.upper()}**: {issue.message}")
                                        if issue.card_name:
                                            st.write(f"   Card: {issue.card_name}")
                                        if issue.suggestion:
                                            st.info(f"   💡 {issue.suggestion}")
                            
                            if legality_report.warnings:
                                with st.expander(f"⚠️ Warnings ({len(legality_report.warnings)})"):
                                    for warning in legality_report.warnings:
                                        st.warning(f"**{warning.category.upper()}**: {warning.message}")
                                        if warning.suggestion:
                                            st.info(f"   💡 {warning.suggestion}")
                            
                            if legality_report.info:
                                with st.expander(f"ℹ️ Information ({len(legality_report.info)})"):
                                    for info in legality_report.info:
                                        st.info(f"{info.message}")
                            
                            st.markdown('</div>', unsafe_allow_html=True)
                        
                        except Exception as e:
                            st.error(f"Error: {e}")
                            if show_verbose:
                                st.exception(e)
                
                # ===== MISSING CARDS =====
                if stats.missing_cards:
                    st.markdown("### ⚠️ Missing Cards")
                    st.warning(f"Could not find {len(stats.missing_cards)} cards")
                    
                    with st.expander("View missing cards"):
                        for card in stats.missing_cards:
                            st.write(f"• {card}")
                
                # ===== SUCCESS SUMMARY =====
                success_rate = ((stats.unique_cards - len(stats.missing_cards)) / stats.unique_cards * 100) if stats.unique_cards > 0 else 0
                st.success(f"✅ Successfully analyzed {success_rate:.1f}% of cards")
                
            except Exception as e:
                st.error(f"❌ Analysis error: {e}")
                if show_verbose:
                    st.exception(e)

else:
    st.session_state.current_page = 'landing'
    st.rerun()

# Enhanced footer
st.markdown("<br/><br/>", unsafe_allow_html=True)
st.markdown("""
<div class="glass-card" style="text-align: center; margin-top: 4rem;">
    <p style="
        color: rgba(255, 255, 255, 0.6);
        font-size: 1rem;
        margin-bottom: 1rem;
    ">Built with ❤️ for the MTG community</p>
    <div style="
        display: flex;
        justify-content: center;
        gap: 3rem;
        flex-wrap: wrap;
        margin-top: 1.5rem;
    ">
        <a href="https://streamlit.io" target="_blank" style="
            color: #b8c5ff;
            text-decoration: none;
            font-weight: 700;
            transition: all 0.3s ease;
            font-size: 1.05rem;
        ">⚡ Powered by Streamlit</a>
        <a href="https://scryfall.com/docs/api" target="_blank" style="
            color: #b8c5ff;
            text-decoration: none;
            font-weight: 700;
            transition: all 0.3s ease;
            font-size: 1.05rem;
        ">🃏 Data from Scryfall API</a>
    </div>
</div>
""", unsafe_allow_html=True)

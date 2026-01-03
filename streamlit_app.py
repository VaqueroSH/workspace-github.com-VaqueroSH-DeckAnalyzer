#!/usr/bin/env python3
"""
MTG Deck Analyzer V2 - Complete Analysis Suite
Full integration of all V2 modules with working analysis pipeline
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Optional, Dict, List, Any, Set
import traceback
import tempfile
import os

# Import all V2 modules
from bracket import evaluate_bracket, BracketResult
from consistency import calculate_consistency, ConsistencyResult
from curve_eval import evaluate_curve, Card as CurveCard, EvalContext
from roles import assign_roles, summarize_roles, Deck as RoleDeck, Card as RoleCard, Role
from synergy import evaluate_synergy
from deck_warnings import (
    WarningContext, evaluate_warnings, detect_problematic_cards, 
    Severity, generate_warnings_summary
)
from tagger import tag_many, filter_by_tag, count_tag

# Import existing modules
from scryfall_api import ScryfallAPI
from deck_parser import parse_decklist


# Initialize API
api = ScryfallAPI()

# Page configuration
st.set_page_config(
    page_title="🃏 MTG Deck Analyzer V2",
    page_icon="🃏",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ===== ENHANCED CSS =====
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800;900&display=swap');
    
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
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
    
    .glass-card {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(20px);
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        padding: 1.5rem;
        margin: 1rem 0;
        transition: all 0.3s ease;
    }
    
    .glass-card:hover {
        background: rgba(255, 255, 255, 0.05);
        border-color: rgba(102, 126, 234, 0.3);
        box-shadow: 0 12px 48px rgba(102, 126, 234, 0.2);
        transform: translateY(-2px);
    }
    
    [data-testid="stMetricValue"] {
        font-size: 2.5rem;
        font-weight: 900;
        background: linear-gradient(135deg, #667eea 0%, #a78bfa 50%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -1px;
    }
    
    [data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        font-weight: 600;
        color: rgba(255, 255, 255, 0.7);
        text-transform: uppercase;
        letter-spacing: 1.5px;
    }
    
    h1 {
        font-size: 4rem !important;
        font-weight: 900 !important;
        background: linear-gradient(135deg, #667eea 0%, #a78bfa 50%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2rem !important;
        letter-spacing: -2px;
    }
    
    h2 {
        font-size: 2rem !important;
        font-weight: 800 !important;
        color: #ffffff;
        margin-top: 2rem !important;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid rgba(102, 126, 234, 0.3);
    }
    
    h3 {
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        color: rgba(255, 255, 255, 0.9);
        margin-top: 1.5rem !important;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.75rem 2rem;
        font-weight: 700;
        font-size: 1rem;
        letter-spacing: 0.5px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
    }
    
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        font-weight: 600;
        color: rgba(255, 255, 255, 0.9);
    }
    
    .stTextArea textarea {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        color: white;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 0.75rem 1.5rem;
        font-weight: 600;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-color: transparent;
    }
    
    .stProgress > div > div > div > div {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
</style>
""", unsafe_allow_html=True)

# ===== HELPER FUNCTIONS =====

def severity_to_emoji(severity: Severity) -> str:
    """Map severity to emoji"""
    if severity == Severity.CRITICAL:
        return "🔴"
    elif severity == Severity.HIGH:
        return "🟠"
    elif severity == Severity.WARN:
        return "🟡"
    else:
        return "🔵"

def create_bar_chart(x: List[str], y: List[float], title: str, color: str = '#667eea'):
    """Create a styled bar chart"""
    fig = go.Figure(data=[go.Bar(
        x=x,
        y=y,
        marker=dict(
            color=color,
            line=dict(color='rgba(255,255,255,0.2)', width=1)
        ),
        text=[f"{val:.0f}" if val > 0 else "" for val in y],
        textposition='outside',
        textfont=dict(size=14, color='white', family='Inter')
    )])
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=20, color='white', family='Inter')),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white', family='Inter'),
        xaxis=dict(gridcolor='rgba(255,255,255,0.1)', title_font=dict(size=14)),
        yaxis=dict(gridcolor='rgba(255,255,255,0.1)', title_font=dict(size=14)),
        height=400,
        margin=dict(t=60, b=60, l=60, r=20)
    )
    
    return fig

def create_donut_chart(values: List[float], labels: List[str], title: str, colors: Optional[List[str]] = None):
    """Create a styled donut chart"""
    if colors is None:
        colors = ['#667eea', '#a78bfa', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe']
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        marker=dict(colors=colors, line=dict(color='rgba(255,255,255,0.2)', width=2)),
        textfont=dict(size=14, color='white', family='Inter'),
        hovertemplate='<b>%{label}</b><br>%{value}<br>%{percent}<extra></extra>'
    )])
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=20, color='white', family='Inter'), x=0.5, xanchor='center'),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white', family='Inter'),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5,
            font=dict(size=12)
        ),
        height=400,
        margin=dict(t=60, b=60, l=20, r=20)
    )
    
    return fig

# ===== ANALYSIS PIPELINE =====

def run_complete_analysis(deck, commander_name: str, bracket_target: str) -> Dict[str, Any]:
    """
    Run complete V2 analysis pipeline on deck.
    Returns dict with all analysis results.
    """
    
    results = {
        'success': False,
        'error': None,
        'bracket': None,
        'consistency': None,
        'curve': None,
        'roles': None,
        'synergy': None,
        'warnings': None,
        'tags': None,
        'card_data': []
    }
    
    try:
        # Step 1: Fetch Scryfall data for all cards
        st.write("📥 Fetching card data from Scryfall...")
        progress_bar = st.progress(0)
        
        card_data = []
        total_cards = len(deck.cards)
        
        for i, (card_name, quantity) in enumerate(deck.cards.items()):
            try:
                card_info = api.get_card(card_name)
                if card_info:
                    card_data.append({
                        'name': card_info.name,
                        'type_line': card_info.type_line,
                        'oracle_text': card_info.oracle_text or '',
                        'cmc': card_info.mana_value,
                        'colors': list(card_info.colors) if card_info.colors else [],
                        'color_identity': list(card_info.color_identity) if card_info.color_identity else [],
                        'keywords': list(card_info.keywords) if card_info.keywords else [],
                        'mana_cost': card_info.mana_cost or '',
                        'quantity': quantity
                    })
                progress_bar.progress((i + 1) / total_cards)
            except Exception as e:
                st.warning(f"⚠️ Could not fetch {card_name}: {str(e)}")
        
        results['card_data'] = card_data
        
        if not card_data:
            results['error'] = "No valid cards found in decklist"
            return results
        
        # Step 2: Tag all cards
        st.write("🏷️ Tagging cards...")
        card_tags = tag_many(card_data)
        results['tags'] = card_tags
        
        # Step 3: Bracket Analysis
        st.write("📊 Evaluating bracket...")
        card_names = [c['name'] for c in card_data]
        bracket_result = evaluate_bracket(card_names)
        results['bracket'] = bracket_result
        
        # Step 4: Role Classification
        st.write("🎭 Classifying card roles...")
        role_deck = RoleDeck(
            cards=[
                RoleCard(
                    name=c['name'],
                    cmc=c['cmc'],
                    type_line=c['type_line'],
                    oracle_text=c['oracle_text'],
                    keywords=set(c['keywords']),
                    colors=set(c['colors']),
                    mana_cost=c.get('mana_cost', '')
                )
                for c in card_data
            ]
        )
        card_roles = assign_roles(role_deck)
        role_summary = summarize_roles(card_roles)
        results['roles'] = role_summary
        results['card_roles'] = card_roles
        
        # Step 5: Curve Evaluation
        st.write("📈 Analyzing mana curve...")
        curve_cards = [
            CurveCard(
                name=c['name'],
                cmc=c['cmc'],
                type_line=c['type_line'],
                oracle_text=c['oracle_text'],
                colors=set(c.get('colors', [])),
                mana_cost=c.get('mana_cost', ''),
                qty=c['quantity']
            )
            for c in card_data
        ]
        
        # Determine commander CMC if provided
        commander_cmc = 0
        if commander_name:
            for c in card_data:
                if c['name'].lower() == commander_name.lower():
                    commander_cmc = c['cmc']
                    break
        
        curve_context = EvalContext(
            commander_cmc=commander_cmc,
            commander_centric_count=0
        )
        curve_result = evaluate_curve(curve_cards, curve_context)
        results['curve'] = curve_result
        
        # Step 6: Consistency Scoring
        st.write("🎯 Calculating consistency...")
        
        # Build role distribution for consistency
        role_dist = {}
        for role in Role:
            count = role_summary.role_counts.get(role, 0)
            if count > 0:
                role_dist[role.name] = count
        
        # Calculate average CMC
        nonland_cards = [c for c in card_data if 'Land' not in c['type_line']]
        avg_cmc = sum(c['cmc'] for c in nonland_cards) / len(nonland_cards) if nonland_cards else 0
        
        land_count = sum(1 for c in card_data if 'Land' in c['type_line'])
        
        consistency_result = calculate_consistency(
            deck_cards=[c['name'] for c in card_data],
            role_distribution=role_dist,
            avg_cmc=avg_cmc,
            land_count=land_count
        )
        results['consistency'] = consistency_result
        
        # Step 7: Synergy Detection
        st.write("🔮 Detecting synergies...")
        counts = {c['name']: c['quantity'] for c in card_data}
        
        # Get commander if provided
        commander_card = None
        if commander_name:
            for c in card_data:
                if c['name'].lower() == commander_name.lower():
                    commander_card = c
                    break
        
        synergy_result = evaluate_synergy(card_data, counts, commander_cards=[commander_card] if commander_card else None)
        results['synergy'] = synergy_result
        
        # Step 8: Generate Warnings
        st.write("⚠️ Checking for warnings...")
        
        warning_ctx = WarningContext(
            bracket_target=bracket_target,
            deck_size=len(card_data),
            commanders=[commander_name] if commander_name else [],
            land_count=role_summary.role_counts.get(Role.LAND, 0),
            ramp_count=role_summary.role_counts.get(Role.RAMP, 0),
            interaction_count=role_summary.role_counts.get(Role.INTERACTION, 0),
            removal_count=role_summary.role_counts.get(Role.REMOVAL, 0),
            boardwipe_count=role_summary.role_counts.get(Role.BOARD_WIPE, 0),
            counterspell_count=role_summary.role_counts.get(Role.COUNTERSPELL, 0),
            tutor_count=role_summary.role_counts.get(Role.TUTOR, 0),
            draw_count=role_summary.role_counts.get(Role.CARD_DRAW, 0),
            protection_count=role_summary.role_counts.get(Role.PROTECTION, 0),
            game_changers=bracket_result.game_changers_found,
            fast_mana=filter_by_tag(card_tags, 'fast_mana'),
            extra_turns=filter_by_tag(card_tags, 'extra_turns'),
            mld=filter_by_tag(card_tags, 'mld'),
            stax_pieces=filter_by_tag(card_tags, 'stax'),
            avg_cmc=avg_cmc,
            tapland_count=count_tag(card_tags, 'tapland') if 'tapland' in str(card_tags) else 0,
            curve_report=curve_result,
            consistency_result=consistency_result,
            synergy_report=synergy_result,
            roles_summary=role_summary
        )
        
        warnings_result = evaluate_warnings(warning_ctx)
        results['warnings'] = warnings_result
        
        results['success'] = True
        st.success("✅ Analysis complete!")
        
    except Exception as e:
        results['error'] = str(e)
        results['traceback'] = traceback.format_exc()
        st.error(f"❌ Analysis failed: {str(e)}")
    
    return results

# ===== DISPLAY FUNCTIONS =====

def display_warnings(warnings_report):
    """Display warnings tab"""
    st.markdown("### ⚠️ Warnings & Issues")
    
    if not warnings_report or not warnings_report.items:
        st.success("✅ No warnings detected - deck looks clean!")
        return
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    by_severity = warnings_report.by_severity()
    
    with col1:
        critical = len(by_severity.get(Severity.CRITICAL, []))
        st.metric("🔴 Critical", critical)
    with col2:
        high = len(by_severity.get(Severity.HIGH, []))
        st.metric("🟠 High", high)
    with col3:
        warn = len(by_severity.get(Severity.WARN, []))
        st.metric("🟡 Warnings", warn)
    with col4:
        info = len(by_severity.get(Severity.INFO, []))
        st.metric("🔵 Info", info)
    
    st.markdown("---")
    
    # Display warnings by severity
    for severity in [Severity.CRITICAL, Severity.HIGH, Severity.WARN, Severity.INFO]:
        warnings_list = by_severity.get(severity, [])
        if not warnings_list:
            continue
        
        emoji = severity_to_emoji(severity)
        expanded = severity in [Severity.CRITICAL, Severity.HIGH]
        
        with st.expander(f"{emoji} {severity.value.upper()} ({len(warnings_list)})", expanded=expanded):
            for warning in warnings_list:
                st.markdown(f"**{warning.title}**")
                st.write(warning.detail)
                
                if warning.evidence:
                    with st.expander("📋 Evidence", expanded=False):
                        for evidence in warning.evidence[:10]:
                            st.write(f"• {evidence}")
                        if len(warning.evidence) > 10:
                            st.write(f"... and {len(warning.evidence) - 10} more")
                
                if warning.suggestion:
                    st.info(f"💡 **Suggestion:** {warning.suggestion}")
                
                st.markdown("---")

def display_bracket_analysis(bracket_result: BracketResult, card_tags):
    """Display bracket analysis tab"""
    st.markdown("### 📊 Bracket Classification")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Bracket display
        bracket_emoji = "🟢" if bracket_result.minimum_bracket in ["B1", "B2"] else "🟡" if bracket_result.minimum_bracket == "B3" else "🔴"
        
        st.markdown(f"""
        <div class='glass-card' style='text-align: center;'>
            <h2 style='font-size: 5rem; margin: 2rem 0;'>{bracket_emoji} {bracket_result.minimum_bracket}</h2>
            <p style='font-size: 1.5rem; color: rgba(255,255,255,0.7); margin-bottom: 2rem;'>
                Minimum Bracket
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"**Game Changers Found:** {bracket_result.game_changer_count}")
        
        if bracket_result.game_changers_found:
            st.markdown("**Game Changer Cards:**")
            for gc in bracket_result.game_changers_found:
                st.write(f"• {gc}")
        
        if bracket_result.is_cedh:
            st.warning("🏆 **cEDH Detected:** This deck contains cEDH signpost cards")
    
    with col2:
        st.markdown("**Power Level Indicators**")
        
        fast_mana_count = count_tag(card_tags, 'fast_mana')
        st.metric("⚡ Fast Mana", fast_mana_count)
        
        tutor_count = count_tag(card_tags, 'tutor:library_search')
        st.metric("🔍 Tutors", tutor_count)
        
        interaction_count = count_tag(card_tags, 'interaction:counterspell')
        st.metric("🛡️ Free Interaction", interaction_count)

def display_consistency_analysis(consistency_result: ConsistencyResult):
    """Display consistency analysis tab"""
    st.markdown("### 🎯 Consistency Analysis")
    
    # Overall score
    col1, col2 = st.columns([1, 2])
    
    with col1:
        score_color = "#22c55e" if consistency_result.score >= 70 else "#fbbf24" if consistency_result.score >= 50 else "#ef4444"
        st.markdown(f"""
        <div class='glass-card' style='text-align: center;'>
            <h2 style='font-size: 5rem; margin: 2rem 0; color: {score_color};'>{consistency_result.score:.0f}</h2>
            <p style='font-size: 1.5rem; color: rgba(255,255,255,0.7);'>Consistency Score</p>
            <p style='font-size: 1.2rem; color: rgba(255,255,255,0.5); margin-top: 1rem;'>{consistency_result.level.value}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Component breakdown
        st.markdown("**Component Breakdown**")
        
        components = [
            ("Card Access", consistency_result.metrics.access_score, 30),
            ("Redundancy", consistency_result.metrics.redundancy_score, 25),
            ("Mana Base", consistency_result.metrics.mana_score, 25),
            ("Speed", consistency_result.metrics.speed_score, 15)
        ]
        
        for name, score, max_score in components:
            pct = (score / max_score) * 100 if max_score > 0 else 0
            st.progress(min(pct / 100, 1.0), text=f"{name}: {score:.1f}/{max_score}")
    
    # Strengths and weaknesses
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("**✅ Strengths**")
        for strength in consistency_result.strengths:
            st.success(strength)
        
        if not consistency_result.strengths:
            st.info("No major strengths identified")
    
    with col4:
        st.markdown("**❌ Weaknesses**")
        for weakness in consistency_result.weaknesses:
            st.error(weakness)
        
        if not consistency_result.weaknesses:
            st.success("No major weaknesses identified")

def display_curve_analysis(curve_result):
    """Display curve analysis tab"""
    st.markdown("### 📈 Mana Curve Analysis")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.metric("Curve Score", f"{curve_result.curve_score:.0f}/100", delta=curve_result.level)
        st.metric("Average MV", f"{curve_result.avg_mv:.2f}")
        st.metric("Effective Mana", f"{curve_result.effective_mana_sources:.0f}")
        
        if hasattr(curve_result, 'shape_category'):
            st.metric("Curve Shape", curve_result.shape_category)
    
    with col2:
        # Mana curve distribution
        if hasattr(curve_result, 'mv_distribution') and curve_result.mv_distribution:
            mv_labels = [f"MV {mv}" for mv in sorted(curve_result.mv_distribution.keys())]
            mv_values = [curve_result.mv_distribution[mv] for mv in sorted(curve_result.mv_distribution.keys())]
            
            fig = create_bar_chart(mv_labels, mv_values, "Mana Value Distribution", '#667eea')
            st.plotly_chart(fig, use_container_width=True)
    
    # Warnings
    if hasattr(curve_result, 'warnings') and curve_result.warnings:
        st.markdown("**⚠️ Curve Warnings**")
        for warning in curve_result.warnings:
            st.warning(warning)

def display_roles_and_synergy(role_summary, synergy_result, card_roles):
    """Display roles and synergy tab"""
    st.markdown("### 🎭 Roles & Synergy")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Role Distribution**")
        
        # Get top roles
        role_counts = [(role.name, count) for role, count in role_summary.role_counts.items() if count > 0]
        role_counts.sort(key=lambda x: -x[1])
        
        if role_counts:
            # Create pie chart
            labels = [r[0] for r in role_counts[:8]]
            values = [r[1] for r in role_counts[:8]]
            
            fig = create_donut_chart(values, labels, "Top Roles")
            st.plotly_chart(fig, use_container_width=True)
            
            # List all roles
            with st.expander("📋 All Roles", expanded=False):
                for role_name, count in role_counts:
                    st.write(f"**{role_name}:** {count}")
        else:
            st.info("No roles detected")
    
    with col2:
        if synergy_result and synergy_result.primary_packages:
            st.markdown("**Primary Strategies**")
            
            for pkg in synergy_result.primary_packages[:3]:
                with st.expander(f"🎯 {pkg.name.title()} ({pkg.score:.0f}/100)", expanded=True):
                    st.write(f"**Total Signals:** {pkg.total_signals:.1f}")
                    
                    st.markdown("**Components:**")
                    for comp in pkg.components:
                        coverage_pct = comp.coverage_ratio * 100
                        status = "✅" if comp.coverage_ratio >= 0.8 else "⚠️" if comp.coverage_ratio >= 0.5 else "❌"
                        st.write(f"{status} {comp.name}: {comp.count}/{comp.min_required} ({coverage_pct:.0f}%)")
                    
                    if pkg.missing:
                        st.markdown("**Missing:**")
                        for miss in pkg.missing[:3]:
                            st.write(f"• {miss}")
        else:
            st.info("No strong synergy packages detected")

def display_card_list(card_data, card_tags, card_roles):
    """Display complete card list tab"""
    st.markdown("### 📋 Complete Card List")
    
    # Create dataframe
    card_list = []
    for card in card_data:
        name = card['name']
        roles = card_roles.get(name)
        tags = card_tags.get(name, set())
        
        role_names = ", ".join(r.name for r in roles.roles) if roles else ""
        tag_list = ", ".join(sorted(tags)[:5]) if tags else ""
        if len(tags) > 5:
            tag_list += f" (+{len(tags) - 5} more)"
        
        card_list.append({
            'Name': name,
            'Type': card['type_line'],
            'CMC': card['cmc'],
            'Roles': role_names,
            'Tags': tag_list
        })
    
    df = pd.DataFrame(card_list)
    st.dataframe(df, use_container_width=True, height=600)
    
    # Export option
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download Card List (CSV)",
        data=csv,
        file_name="deck_analysis.csv",
        mime="text/csv"
    )

# ===== MAIN APP =====

def main():
    # Hero Section
    st.markdown("<h1>🃏 MTG Deck Analyzer V2</h1>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-size: 1.2rem; color: rgba(255,255,255,0.7); margin-bottom: 2rem;'>
        Complete deck analysis with bracket classification, consistency scoring, synergy detection, and more.
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar for input
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")
        
        bracket_target = st.selectbox(
            "Target Bracket",
            options=["B1", "B2", "B3", "B4", "cEDH"],
            index=2,
            help="Select your target power level"
        )
        
        commander_name = st.text_input(
            "Commander Name (optional)",
            placeholder="e.g., Atraxa, Praetors' Voice",
            help="Enter your commander for better analysis"
        )
        
        st.markdown("---")
        st.markdown("### 📝 Decklist")
        st.markdown("Paste your decklist (one card per line with quantity)")
        
        decklist_input = st.text_area(
            "Decklist",
            height=400,
            placeholder="1 Sol Ring\n1 Command Tower\n1 Rhystic Study\n...",
            label_visibility="collapsed"
        )
        
        analyze_button = st.button("🔍 Analyze Deck", use_container_width=True)
    
    # Main content area
    if not analyze_button:
        # Landing page
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class='glass-card'>
                <h3>📊 Bracket Analysis</h3>
                <p>Automatic bracket classification based on Game Changers v1.1 with cEDH detection</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class='glass-card'>
                <h3>🎯 Consistency Scoring</h3>
                <p>Measure deck reliability across 5 components: access, redundancy, mana, speed, and risk</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class='glass-card'>
                <h3>📈 Curve Evaluation</h3>
                <p>Analyze mana curve shape and support with context-aware recommendations</p>
            </div>
            """, unsafe_allow_html=True)
        
        col4, col5, col6 = st.columns(3)
        
        with col4:
            st.markdown("""
            <div class='glass-card'>
                <h3>🎭 Role Classification</h3>
                <p>Identify card roles across 24 categories with explainable reasons</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col5:
            st.markdown("""
            <div class='glass-card'>
                <h3>🔮 Synergy Detection</h3>
                <p>Discover strategy packages and measure how well cards support your plan</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col6:
            st.markdown("""
            <div class='glass-card'>
                <h3>⚠️ Warning System</h3>
                <p>Unified warnings for bracket violations, mana issues, and salt triggers</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("""
        <div style='text-align: center; padding: 2rem; color: rgba(255,255,255,0.5);'>
            <p>👈 Enter your decklist in the sidebar to begin analysis</p>
        </div>
        """, unsafe_allow_html=True)
        
        return
    
    # Parse and analyze
    if not decklist_input.strip():
        st.error("❌ Please enter a decklist")
        return
    
    with st.spinner("🔄 Parsing decklist..."):
        try:
            # Write decklist to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                temp_file.write(decklist_input)
                temp_file_path = temp_file.name
            
            # Parse the file
            deck = parse_decklist(temp_file_path)
            
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            
            if not deck or not deck.cards:
                st.error("❌ Could not parse decklist. Please check format.")
                return
            
            st.success(f"✅ Parsed {len(deck.cards)} cards")
            
        except Exception as e:
            st.error(f"❌ Failed to parse decklist: {str(e)}")
            return
    
    # Run complete analysis
    with st.status("🔄 Running complete V2 analysis...", expanded=True) as status:
        results = run_complete_analysis(deck, commander_name, bracket_target)
        
        if not results['success']:
            status.update(label="❌ Analysis failed", state="error", expanded=True)
            st.error(f"Error: {results.get('error', 'Unknown error')}")
            if results.get('traceback'):
                with st.expander("🐛 Debug Info"):
                    st.code(results['traceback'])
            return
        
        status.update(label="✅ Analysis complete!", state="complete", expanded=False)
    
    # Display summary metrics
    st.markdown("## 📊 Overview")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        bracket = results['bracket']
        bracket_emoji = "🟢" if bracket.minimum_bracket in ["B1", "B2"] else "🟡" if bracket.minimum_bracket == "B3" else "🔴"
        st.metric("Bracket", f"{bracket_emoji} {bracket.minimum_bracket}", delta=f"{bracket.game_changer_count} GCs")
    
    with col2:
        consistency = results['consistency']
        st.metric("Consistency", f"{consistency.score:.0f}/100", delta=consistency.level.value)
    
    with col3:
        curve = results['curve']
        st.metric("Curve Score", f"{curve.curve_score:.0f}/100", delta=curve.level)
    
    with col4:
        synergy = results['synergy']
        synergy_score = synergy.overall_score if synergy else 0
        num_strategies = len(synergy.primary_packages) if synergy and synergy.primary_packages else 0
        st.metric("Synergy", f"{synergy_score:.0f}/100", delta=f"{num_strategies} strategies")
    
    with col5:
        warnings = results['warnings']
        critical_warnings = len(warnings.get_critical())
        high_warnings = len(warnings.get_high())
        total_warnings = len(warnings.items)
        
        if critical_warnings > 0:
            delta_text = f"🔴 {critical_warnings} critical"
        elif high_warnings > 0:
            delta_text = f"🟠 {high_warnings} high"
        else:
            delta_text = "✅ Clean"
        
        st.metric("Warnings", f"{total_warnings}", delta=delta_text)
    
    st.markdown("---")
    
    # Tabbed interface
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "⚠️ Warnings",
        "📊 Bracket & Power",
        "🎯 Consistency",
        "📈 Curve",
        "🎭 Roles & Synergy",
        "📋 Card List"
    ])
    
    with tab1:
        display_warnings(results['warnings'])
    
    with tab2:
        display_bracket_analysis(results['bracket'], results['tags'])
    
    with tab3:
        display_consistency_analysis(results['consistency'])
    
    with tab4:
        display_curve_analysis(results['curve'])
    
    with tab5:
        display_roles_and_synergy(results['roles'], results['synergy'], results['card_roles'])
    
    with tab6:
        display_card_list(results['card_data'], results['tags'], results['card_roles'])

if __name__ == "__main__":
    main()
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

from scryfall_api import ScryfallAPI
from deck_parser import parse_decklist
from models import DeckAnalyzer

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
show_verbose = st.sidebar.checkbox("Show detailed error information", value=False)

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
    temp_file_path = None
    
    try:
        # Create a temporary file for parsing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            temp_file.write(decklist_content)
            temp_file_path = temp_file.name
        
        # Enhanced progress indicators with animations
        progress_container = st.container()
        with progress_container:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Add some visual flair with columns for status
            status_cols = st.columns(4)
            step_indicators = []
            for i, (icon, text) in enumerate([
                ("📄", "Parse"), ("🌐", "API"), ("🔍", "Analyze"), ("✅", "Complete")
            ]):
                with status_cols[i]:
                    step_indicators.append(st.empty())
        
        # Parse the decklist
        status_text.text("📄 Parsing decklist...")
        step_indicators[0].success("📄 Parse")
        progress_bar.progress(20)
        deck = parse_decklist(temp_file_path)
        
        # Initialize API and analyzer
        status_text.text("🌐 Connecting to Scryfall API...")
        step_indicators[1].info("🌐 API")
        progress_bar.progress(40)
        api = ScryfallAPI()
        analyzer = DeckAnalyzer(api)
        
        # Analyze the deck
        status_text.text("🔍 Analyzing deck...")
        step_indicators[2].warning("🔍 Analyze")
        progress_bar.progress(60)
        
        # Analyze the deck (no stdout output from analyzer)
        stats = analyzer.analyze(deck)
        
        progress_bar.progress(100)
        status_text.text("✅ Analysis complete!")
        step_indicators[3].success("✅ Complete")
        
        # Clear progress indicators after completion
        time.sleep(1)
        progress_container.empty()
        
        # Display results - this section is now outside the try block to ensure it always shows
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
                # Create color chart with MTG colors
                color_mapping = {
                    'W': '#FFFBD5',  # White/cream
                    'U': '#0E68AB',  # Blue
                    'B': '#150B00',  # Black/dark brown
                    'R': '#D3202A',  # Red
                    'G': '#00733E',  # Green
                    'C': '#CCCCCC'   # Colorless/gray
                }
                
                color_df = []
                for color_code, count in sorted(stats.color_counts.items()):
                    color_name = stats.color_names.get(color_code, color_code)
                    percentage = (count / stats.unique_cards * 100)
                    color_label = f"{color_name} ({color_code})"
                    
                    color_df.append({
                        "Code": color_code,           # single-letter code used for color mapping
                        "Label": color_label,         # human-friendly label shown in the legend and hover
                        "Cards": count, 
                        "Percentage": percentage
                    })
                    
                # Ensure `df` is properly constructed
                df = pd.DataFrame(color_df)

                # Create pie chart for color distribution with explicit color mapping
                fig = px.pie(
                    df,
                    values='Cards',
                    names='Label',          # what users see
                    color='Code',           # what Plotly uses to map colors
                    title="Color Distribution",
                    color_discrete_map=color_mapping
                )
                fig.update_layout(showlegend=True, height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                # Show data table too
                st.dataframe(
                    df[["Label", "Cards", "Percentage"]].assign(Percentage=lambda d: (d["Percentage"]).map(lambda x: f"{x:.1f}%")),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No colored cards found - this appears to be a colorless deck")
        
        with st.expander("📈 Mana Curve", expanded=True):
            if stats.mana_curve:
                # Create two columns for average CMC and ideal curve info
                curve_col1, curve_col2 = st.columns(2)
                
                with curve_col1:
                    st.metric("⚡ Average CMC", f"{stats.average_mana_value:.2f}")
                
                with curve_col2:
                    nonland_count = sum(stats.mana_curve.values())
                    st.metric("🃏 Nonland Cards", nonland_count)
                
                # Create enhanced mana curve data
                curve_data = []
                all_cmc_values = list(range(8))  # 0-7+
                
                for cmc in all_cmc_values:
                    if cmc == 7:
                        # Handle 7+ CMC
                        high_cmc_count = sum(stats.mana_curve.get(i, 0) for i in range(7, 20))
                        curve_data.append({"CMC": "7+", "Cards": high_cmc_count, "CMC_Sort": 7})
                    else:
                        count = stats.mana_curve.get(cmc, 0)
                        curve_data.append({"CMC": str(cmc), "Cards": count, "CMC_Sort": cmc})
                
                df = pd.DataFrame(curve_data)
                
                # Create interactive bar chart
                fig = px.bar(df, x='CMC', y='Cards', 
                            title="Mana Curve Distribution",
                            color='Cards',
                            color_continuous_scale='blues')
                
                # Customize the chart
                fig.update_layout(
                    xaxis_title="Converted Mana Cost",
                    yaxis_title="Number of Cards",
                    showlegend=False,
                    height=400
                )
                
                fig.update_traces(
                    texttemplate='%{y}', 
                    textposition='outside',
                    hovertemplate='<b>%{x} CMC</b><br>Cards: %{y}<extra></extra>'
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Show ideal curve guidance
                st.info("💡 **Ideal Curve Tips**: Most decks want more low-cost cards (1-3 CMC) than high-cost cards for consistent gameplay.")
                
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
                        percentage = (count / stats.unique_cards * 100) if stats.unique_cards > 0 else 0
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
                # Create enhanced card type visualization
                type_data = []
                sorted_types = sorted(stats.card_types.items(), key=lambda x: (-x[1], x[0]))
                
                for card_type, count in sorted_types:
                    percentage = (count / stats.unique_cards * 100)
                    type_data.append({
                        "Type": card_type, 
                        "Cards": count, 
                        "Percentage": percentage
                    })
                
                df = pd.DataFrame(type_data)
                
                # Create horizontal bar chart for card types
                fig = px.bar(df, x='Cards', y='Type', 
                            title="Card Types Distribution",
                            orientation='h',
                            color='Cards',
                            color_continuous_scale='viridis')
                
                fig.update_layout(
                    xaxis_title="Number of Cards",
                    yaxis_title="Card Type",
                    height=max(300, len(sorted_types) * 50),
                    showlegend=False
                )
                
                fig.update_traces(
                    texttemplate='%{x}', 
                    textposition='outside',
                    hovertemplate='<b>%{y}</b><br>Cards: %{x}<extra></extra>'
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Show data table with percentages
                df_display = df.copy()
                df_display['Percentage'] = df_display['Percentage'].apply(lambda x: f"{x:.1f}%")
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
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
                
    except Exception as e:
        st.error(f"❌ Error analyzing deck: {e}")
        if show_verbose:
            st.exception(e)
            
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
            
    
# Footer
st.markdown("---")
st.markdown("### 🎉 Share Your Results!")
st.markdown("Built with ❤️ using [Streamlit](https://streamlit.io) and [Scryfall API](https://scryfall.com/docs/api)")

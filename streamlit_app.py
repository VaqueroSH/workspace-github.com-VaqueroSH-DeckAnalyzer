#!/usr/bin/env python3
"""
Streamlit MTG Deck Analyzer - Web App Version
"""

import streamlit as st
from pathlib import Path
import tempfile
import os
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# Added for export PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import io
import json
import zipfile

from scryfall_api import ScryfallAPI
from deck_parser import parse_decklist
from models import DeckAnalyzer

# Utility: generate a simple PDF report for the analyzed deck
# Returns a BytesIO buffer ready to be used in a Streamlit download_button

def generate_pdf_report(deck, stats):
    styles = getSampleStyleSheet()
    buffer = io.BytesIO()
    
    try:
        doc = SimpleDocTemplate(buffer, pagesize=letter)

        elements = []

        deck_name = getattr(deck, 'name', 'Deck') or 'Deck'
        elements.append(Paragraph(f"{deck_name} - Analysis Report", styles['Title']))
        elements.append(Spacer(1, 12))

        # Summary
        summary = (
            f"Total Cards: {stats.total_cards} | "
            f"Unique: {stats.unique_cards} | "
            f"Lands: {stats.lands} | "
            f"Nonlands: {stats.nonlands} | "
            f"Avg CMC: {stats.average_mana_value:.2f} | "
            f"Total Value: ${stats.total_deck_value:.2f}"
        )
        elements.append(Paragraph("Summary", styles['Heading2']))
        elements.append(Paragraph(summary, styles['Normal']))
        elements.append(Spacer(1, 10))

        # Color distribution
        elements.append(Paragraph("Color Distribution", styles['Heading2']))
        if getattr(stats, 'color_counts', None):
            color_lines = []
            for c, cnt in stats.color_counts.items():
                color_name = stats.color_names.get(c, c)
                color_lines.append(f"• {color_name} ({c}): {cnt}")
            elements.append(Paragraph("<br/>".join(color_lines), styles['Normal']))
        else:
            elements.append(Paragraph("Colorless or no color data.", styles['Normal']))
        elements.append(Spacer(1, 8))

        # Mana curve
        elements.append(Paragraph("Mana Curve", styles['Heading2']))
        if getattr(stats, 'mana_curve', None):
            curve_lines = []
            for mv in sorted(stats.mana_curve.keys()):
                label = "7+" if mv >= 7 else str(mv)
                curve_lines.append(f"• {label} CMC: {stats.mana_curve[mv]}")
            elements.append(Paragraph("<br/>".join(curve_lines), styles['Normal']))
        else:
            elements.append(Paragraph("No nonland cards to analyze.", styles['Normal']))
        elements.append(Spacer(1, 8))

        # Card types
        elements.append(Paragraph("Card Types", styles['Heading2']))
        if getattr(stats, 'card_types', None):
            type_lines = []
            for t, cnt in sorted(stats.card_types.items(), key=lambda x: (-x[1], x[0])):
                pct = (cnt / stats.unique_cards * 100) if stats.unique_cards else 0
                type_lines.append(f"• {t}: {cnt} ({pct:.1f}%)")
            elements.append(Paragraph("<br/>".join(type_lines), styles['Normal']))
        else:
            elements.append(Paragraph("No card type data available.", styles['Normal']))
        elements.append(Spacer(1, 8))

        # Rarity
        elements.append(Paragraph("Rarity Breakdown", styles['Heading2']))
        if getattr(stats, 'rarity_counts', None):
            rarity_lines = []
            for r, cnt in stats.rarity_counts.items():
                rarity_lines.append(f"• {r.title()}: {cnt}")
            elements.append(Paragraph("<br/>".join(rarity_lines), styles['Normal']))
        else:
            elements.append(Paragraph("No rarity data available.", styles['Normal']))
        elements.append(Spacer(1, 8))

        # Interaction suite
        elements.append(Paragraph("Interaction Suite", styles['Heading2']))
        if getattr(stats, 'interaction_counts', None):
            inter_lines = []
            for k in ['Removal', 'Tutors', 'Card Draw', 'Ramp', 'Protection']:
                if k in stats.interaction_counts:
                    examples = stats.interaction_cards.get(k, [])[:5]
                    example_str = ", ".join(examples)
                    if len(stats.interaction_cards.get(k, [])) > 5:
                        example_str += ", ..."
                    inter_lines.append(f"• {k}: {stats.interaction_counts[k]}" + (f" — {example_str}" if example_str else ""))
            if inter_lines:
                elements.append(Paragraph("<br/>".join(inter_lines), styles['Normal']))
            else:
                elements.append(Paragraph("No interaction cards identified.", styles['Normal']))
        else:
            elements.append(Paragraph("No interaction data available.", styles['Normal']))
        elements.append(Spacer(1, 8))

        # Most expensive cards
        elements.append(Paragraph("Most Expensive Cards", styles['Heading2']))
        if getattr(stats, 'most_expensive_cards', None):
            price_lines = [f"• {name}: ${price:.2f}" for name, price in stats.most_expensive_cards]
            elements.append(Paragraph("<br/>".join(price_lines), styles['Normal']))
        else:
            elements.append(Paragraph("Price information not available.", styles['Normal']))
        elements.append(Spacer(1, 8))

        # Missing cards
        if getattr(stats, 'missing_cards', None):
            if stats.missing_cards:
                elements.append(Paragraph(f"Missing Cards ({len(stats.missing_cards)})", styles['Heading2']))
                miss_lines = [f"• {c}" for c in stats.missing_cards]
                elements.append(Paragraph("<br/>".join(miss_lines), styles['Normal']))
                elements.append(Spacer(1, 8))

        # Build the document
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
    finally:
        buffer.close()

# Utility: CSV export of the raw decklist (Card, Quantity, Set)
# Returns raw bytes suitable for download_button

def generate_csv_export(deck):
    lines = ["Card,Quantity,Set"]
    for card in sorted(deck.cards.keys()):
        qty = deck.cards[card]
        set_code = deck.card_sets.get(card, "")
        safe_card = card.replace('"', '""')
        lines.append(f'"{safe_card}",{qty},"{set_code}"')
    data = "\n".join(lines)
    return data.encode("utf-8")

# Utility: JSON export of summary stats and deck metadata
# Returns raw bytes suitable for download_button

def generate_json_export(deck, stats):
    payload = {
        "deck": {
            "name": getattr(deck, "name", None),
            "commander": getattr(deck, "commander", None),
            "total_cards": deck.total_cards,
            "unique_cards": deck.unique_cards,
            "cards": deck.cards,
            "card_sets": deck.card_sets,
        },
        "stats": {
            "total_cards": stats.total_cards,
            "unique_cards": stats.unique_cards,
            "lands": stats.lands,
            "nonlands": stats.nonlands,
            "color_counts": stats.color_counts,
            "mana_curve": stats.mana_curve,
            "average_mana_value": stats.average_mana_value,
            "card_types": stats.card_types,
            "total_deck_value": stats.total_deck_value,
            "most_expensive_cards": stats.most_expensive_cards,
            "rarity_counts": stats.rarity_counts,
            "interaction_counts": stats.interaction_counts,
            "interaction_cards": stats.interaction_cards,
            "set_counts": stats.set_counts,
            "set_names": stats.set_names,
            "missing_cards": stats.missing_cards,
        }
    }
    return json.dumps(payload, indent=2).encode("utf-8")

# New: ZIP export that packages PDF, CSV, and JSON

def generate_zip_export(deck, stats):
    deck_name = getattr(deck, 'name', 'deck') or 'deck'
    deck_name = "".join(c for c in deck_name if c.isalnum() or c in (' ', '-', '_')).strip()
    if not deck_name:
        deck_name = 'deck'
        
    zip_buffer = io.BytesIO()
    
    try:
        with zipfile.ZipFile(zip_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            # PDF export
            pdf_data = generate_pdf_report(deck, stats)
            zf.writestr(f"{deck_name}_analysis.pdf", pdf_data)
            
            # CSV export
            csv_data = generate_csv_export(deck)
            zf.writestr(f"{deck_name}_deck.csv", csv_data)
            
            # JSON export
            json_data = generate_json_export(deck, stats)
            zf.writestr(f"{deck_name}_summary.json", json_data)
            
        zip_buffer.seek(0)
        return zip_buffer.getvalue()
    finally:
        zip_buffer.close()

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
        
        try:
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
            
            # Export options
            st.markdown("### 📥 Export Options")
            export_cols = st.columns([1, 1, 1, 1])

            # Get sanitized deck name
            deck_name = getattr(deck, 'name', '') or 'deck'
            deck_name = "".join(c for c in deck_name if c.isalnum() or c in (' ', '-', '_')).strip()
            if not deck_name:
                deck_name = 'deck'

            with export_cols[0]:
                # Direct PDF download
                pdf_buffer = generate_pdf_report(deck, stats)
                st.download_button(
                    "📄 Download PDF",
                    data=pdf_buffer,
                    file_name=f"{deck_name}_analysis.pdf",
                    mime="application/pdf",
                    help="Download a formatted PDF report with all analysis results"
                )

            with export_cols[1]:
                # Direct CSV download
                csv_bytes = generate_csv_export(deck)
                st.download_button(
                    "🧾 Download CSV",
                    data=csv_bytes,
                    file_name=f"{deck_name}_deck.csv",
                    mime="text/csv",
                    help="Download the decklist as a CSV file with card names, quantities, and set codes"
                )

            with export_cols[2]:
                # Direct JSON download
                json_bytes = generate_json_export(deck, stats)
                st.download_button(
                    "🧩 Download JSON",
                    data=json_bytes,
                    file_name=f"{deck_name}_summary.json",
                    mime="application/json",
                    help="Download complete analysis data in JSON format"
                )

            with export_cols[3]:
                # Direct ZIP download
                zip_buffer = generate_zip_export(deck, stats)
                st.download_button(
                    "📦 Download All",
                    data=zip_buffer,
                    file_name=f"{deck_name}_exports.zip",
                    mime="application/zip",
                    help="Download all formats (PDF, CSV, JSON) in a single ZIP file"
                )

        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            # Clear progress indicators after a short delay
            import time
            time.sleep(1)
            progress_container.empty()
            
    except Exception as e:
        st.error(f"❌ Error analyzing deck: {e}")
        if show_verbose:
            st.exception(e)

# Footer
st.markdown("---")
st.markdown("### 🎉 Share Your Results!")
st.markdown("Built with ❤️ using [Streamlit](https://streamlit.io) and [Scryfall API](https://scryfall.com/docs/api)")

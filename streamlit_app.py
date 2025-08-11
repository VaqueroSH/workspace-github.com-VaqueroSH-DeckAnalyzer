#!/usr/bin/env python3
"""
Streamlit MTG Deck Analyzer - Web App Version
"""

from pathlib import Path

# Added for export PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
import io
import json
import zipfile
import tempfile
import time
import os
import pandas as pd
import plotly.express as px
import streamlit as st

from scryfall_api import ScryfallAPI
from deck_parser import parse_decklist
from models import DeckAnalyzer

def create_pdf_styles():
    """Create and return custom styles for the PDF report."""
    styles = getSampleStyleSheet()
    
    # Add custom styles
    styles.add(ParagraphStyle(
        name='Title',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER
    ))
    
    styles.add(ParagraphStyle(
        name='section',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=20,
        spaceAfter=10
    ))
    
    styles.add(ParagraphStyle(
        name='body',
        parent=styles['Normal'],
        fontSize=10,
        spaceBefore=5,
        spaceAfter=5
    ))
    
    styles.add(ParagraphStyle(
        name='table_header',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.white,
        alignment=TA_CENTER
    ))
    
    styles.add(ParagraphStyle(
        name='footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.gray,
        alignment=TA_CENTER,
        spaceBefore=0,
        spaceAfter=0
    ))
    
    return styles

def create_pdf_header(deck, styles):
    """Create the PDF header section."""
    elements = []
    deck_name = getattr(deck, 'name', 'Deck Analysis') or 'Deck Analysis'
    elements.append(Paragraph(deck_name, styles['Title']))
    elements.append(Spacer(1, 20))
    return elements

def create_executive_summary(stats, styles):
    """Create the executive summary section."""
    elements = []
    elements.append(Paragraph("Executive Summary", styles['section']))
    
    summary = (
        f"Total Cards: {stats.total_cards}<br/>"
        f"Unique Cards: {stats.unique_cards}<br/>"
        f"Lands: {stats.lands} | Nonlands: {stats.nonlands}<br/>"
        f"Average Mana Value: {stats.average_mana_value:.2f}<br/>"
        f"Total Deck Value: ${stats.total_deck_value:.2f}"
    )
    elements.append(Paragraph(summary, styles['body']))
    elements.append(Spacer(1, 15))
    return elements

def create_color_distribution(stats, styles):
    """Create the color distribution section."""
    elements = []
    elements.append(Paragraph("Color Distribution", styles['section']))
    
    if stats.color_counts:
        color_text = []
        for color, count in sorted(stats.color_counts.items()):
            percentage = (count / stats.unique_cards * 100)
            color_name = stats.color_names.get(color, color)
            color_text.append(f"{color_name} ({color}): {count} cards ({percentage:.1f}%)")
        elements.append(Paragraph("<br/>".join(color_text), styles['body']))
    else:
        elements.append(Paragraph("This appears to be a colorless deck", styles['body']))
    
    elements.append(Spacer(1, 15))
    return elements

def create_mana_curve_analysis(stats, styles):
    """Create the mana curve analysis section."""
    elements = []
    elements.append(Paragraph("Mana Curve Analysis", styles['section']))
    
    if stats.mana_curve:
        curve_text = []
        for cmc in range(max(stats.mana_curve.keys()) + 1):
            count = stats.mana_curve.get(cmc, 0)
            if count > 0:
                curve_text.append(f"CMC {cmc}: {count} cards")
        
        elements.append(Paragraph("<br/>".join(curve_text), styles['body']))
        elements.append(Paragraph(f"Average Mana Value: {stats.average_mana_value:.2f}", styles['body']))
    else:
        elements.append(Paragraph("No nonland cards to analyze", styles['body']))
    
    elements.append(Spacer(1, 15))
    return elements

def create_card_types_section(stats, styles):
    """Create the card types section."""
    elements = []
    elements.append(Paragraph("Card Type Distribution", styles['section']))
    
    if stats.card_types:
        type_text = []
        sorted_types = sorted(stats.card_types.items(), key=lambda x: (-x[1], x[0]))
        for card_type, count in sorted_types:
            percentage = (count / stats.unique_cards * 100)
            type_text.append(f"{card_type}: {count} cards ({percentage:.1f}%)")
        elements.append(Paragraph("<br/>".join(type_text), styles['body']))
    else:
        elements.append(Paragraph("No card type data available", styles['body']))
    
    elements.append(Spacer(1, 15))
    return elements

def create_interaction_suite(stats, styles):
    """Create the interaction suite section."""
    elements = []
    elements.append(Paragraph("Interaction Suite", styles['section']))
    
    if stats.interaction_counts:
        interaction_text = []
        for category in ['Removal', 'Tutors', 'Card Draw', 'Ramp', 'Protection']:
            if category in stats.interaction_counts:
                count = stats.interaction_counts[category]
                examples = stats.interaction_cards.get(category, [])[:3]
                example_str = ", ".join(examples)
                if len(stats.interaction_cards.get(category, [])) > 3:
                    example_str += ", ..."
                interaction_text.append(f"{category}: {count} cards<br/>Examples: {example_str}")
        elements.append(Paragraph("<br/><br/>".join(interaction_text), styles['body']))
    else:
        elements.append(Paragraph("No interaction data available", styles['body']))
    
    elements.append(Spacer(1, 15))
    return elements

def create_expensive_cards_section(stats, styles):
    """Create the most expensive cards section."""
    elements = []
    elements.append(Paragraph("Most Expensive Cards", styles['section']))
    
    if stats.most_expensive_cards:
        price_text = []
        for card, price in stats.most_expensive_cards:
            price_text.append(f"{card}: ${price:.2f}")
        elements.append(Paragraph("<br/>".join(price_text), styles['body']))
    else:
        elements.append(Paragraph("Price information not available", styles['body']))
    
    elements.append(Spacer(1, 15))
    return elements

def create_rarity_distribution(stats, styles):
    """Create the rarity distribution section."""
    elements = []
    elements.append(Paragraph("Rarity Distribution", styles['section']))
    
    if stats.rarity_counts:
        rarity_text = []
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
                rarity_text.append(f"{rarity_display}: {count} cards ({percentage:.1f}%)")
        elements.append(Paragraph("<br/>".join(rarity_text), styles['body']))
    else:
        elements.append(Paragraph("Rarity information not available", styles['body']))
    
    elements.append(Spacer(1, 15))
    return elements

# Utility: generate a simple PDF report for the analyzed deck
# Returns a BytesIO buffer ready to be used in a Streamlit download_button

def generate_pdf_report(deck, stats):
    """Generate a professional, visually appealing PDF report."""
    buffer = io.BytesIO()
    
    try:
        # Create document with custom margins
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=1*inch,
            bottomMargin=1*inch
        )
        
        # Get custom styles
        styles = create_pdf_styles()
        
        # Build all sections
        elements = []
        
        # Add header and title
        elements.extend(create_pdf_header(deck, styles))
        
        # Add executive summary
        elements.extend(create_executive_summary(stats, styles))
        
        # Add color distribution
        elements.extend(create_color_distribution(stats, styles))
        
        # Add mana curve analysis
        elements.extend(create_mana_curve_analysis(stats, styles))
        
        # Add card types breakdown
        elements.extend(create_card_types_section(stats, styles))
        
        # Add interaction suite
        elements.extend(create_interaction_suite(stats, styles))
        
        # Add most expensive cards
        elements.extend(create_expensive_cards_section(stats, styles))
        
        # Add rarity distribution
        elements.extend(create_rarity_distribution(stats, styles))
        
        # Add missing cards (if any)
        if stats.missing_cards:
            elements.append(Paragraph(f"⚠️ Missing Cards ({len(stats.missing_cards)})", styles['section']))
            missing_text = ", ".join(stats.missing_cards[:10])  # Limit to first 10
            if len(stats.missing_cards) > 10:
                missing_text += f"... and {len(stats.missing_cards) - 10} more"
            elements.append(Paragraph(missing_text, styles['body']))
            elements.append(Spacer(1, 15))
        
        # Add footer
        elements.append(Spacer(1, 20))
        generation_time = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        elements.append(Paragraph(f"Report generated on {generation_time} by MTG Deck Analyzer", styles['footer']))
        elements.append(Paragraph("Built with ❤️ using Scryfall API", styles['footer']))
        
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
            
            # Enhanced export options
            st.markdown("## 📥 Export Your Analysis")
            st.markdown("*Save your deck analysis in multiple formats for sharing or future reference*")

            # Create tabs for different export types
            export_tab1, export_tab2, export_tab3 = st.tabs(["📊 Reports", "📋 Data Files", "🎁 Complete Package"])

            # Get sanitized deck name
            deck_name = getattr(deck, 'name', '') or 'deck'
            deck_name = "".join(c for c in deck_name if c.isalnum() or c in (' ', '-', '_')).strip()
            if not deck_name:
                deck_name = 'deck'

            with export_tab1:
                st.markdown("### Professional Reports")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # PDF Export Card
                    st.markdown("""
                    <div style="border: 2px solid #4CAF50; border-radius: 10px; padding: 20px; margin: 10px 0; background-color: #f8fff8;">
                        <h4 style="color: #2E7D32; margin-top: 0;">📄 PDF Analysis Report</h4>
                        <p style="color: #555; margin-bottom: 15px;">
                            Professional formatted report with all statistics, charts, and analysis.
                            Perfect for sharing with friends or keeping records.
                        </p>
                        <ul style="color: #666; margin-bottom: 15px;">
                            <li>✅ Complete deck summary</li>
                            <li>✅ Mana curve breakdown</li>
                            <li>✅ Color distribution</li>
                            <li>✅ Most expensive cards</li>
                            <li>✅ Interaction analysis</li>
                        </ul>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    pdf_buffer = generate_pdf_report(deck, stats)
                    st.download_button(
                        "📄 Generate PDF Report",
                        data=pdf_buffer,
                        file_name=f"{deck_name}_analysis.pdf",
                        mime="application/pdf",
                        help="Download a beautifully formatted PDF report",
                        use_container_width=True
                    )

            with export_tab2:
                st.markdown("### Raw Data Files")
                st.markdown("*Export your deck data for use in spreadsheets, databases, or other applications*")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # CSV Export Card
                    st.markdown("""
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                border-radius: 15px; padding: 25px; color: white; margin: 10px 0;">
                        <h4 style="margin-top: 0; color: white;">🧾 CSV Spreadsheet</h4>
                        <p style="margin-bottom: 15px; opacity: 0.9;">
                            Clean spreadsheet format with card names, quantities, and set codes.
                            Open in Excel, Google Sheets, or any spreadsheet app.
                        </p>
                        <div style="background: rgba(255,255,255,0.1); padding: 10px; border-radius: 8px; margin-bottom: 15px;">
                            <small>📊 Perfect for: Price tracking, inventory management, deck comparisons</small>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    csv_bytes = generate_csv_export(deck)
                    st.download_button(
                        "🧾 Download CSV",
                        data=csv_bytes,
                        file_name=f"{deck_name}_deck.csv",
                        mime="text/csv",
                        help="Download the decklist as a CSV file",
                        use_container_width=True
                    )
                
                with col2:
                    # JSON Export Card
                    st.markdown("""
                    <div style="background: linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%); 
                                border-radius: 15px; padding: 25px; color: white; margin: 10px 0;">
                        <h4 style="margin-top: 0; color: white;">🧩 JSON Data</h4>
                        <p style="margin-bottom: 15px; opacity: 0.9;">
                            Complete deck data in JSON format.
                            Perfect for programmatic analysis or importing into other tools.
                        </p>
                        <div style="background: rgba(255,255,255,0.1); padding: 10px; border-radius: 8px; margin-bottom: 15px;">
                            <small>🔧 Ideal for: Developers, data analysis, custom tools</small>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    json_bytes = generate_json_export(deck, stats)
                    st.download_button(
                        "🧩 Download JSON",
                        data=json_bytes,
                        file_name=f"{deck_name}_summary.json",
                        mime="application/json",
                        help="Download complete analysis data",
                        use_container_width=True
                    )

            with export_tab3:
                st.markdown("### Complete Package")
                st.markdown("*Get everything in one convenient ZIP archive*")
                
                st.markdown("""
                <div style="background: linear-gradient(135deg, #FF6B6B 0%, #FFE66D 100%); 
                            border-radius: 15px; padding: 25px; color: white; margin: 10px 0;">
                    <h4 style="margin-top: 0; color: white;">📦 All-in-One Package</h4>
                    <p style="margin-bottom: 15px; opacity: 0.9;">
                        Download everything in a single ZIP file:
                        • Professional PDF report
                        • CSV spreadsheet
                        • JSON data export
                    </p>
                    <div style="background: rgba(255,255,255,0.1); padding: 10px; border-radius: 8px;">
                        <small>💡 Perfect for: Archiving, sharing, or using multiple formats</small>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                zip_buffer = generate_zip_export(deck, stats)
                st.download_button(
                    "📦 Download Complete Package",
                    data=zip_buffer,
                    file_name=f"{deck_name}_exports.zip",
                    mime="application/zip",
                    help="Download all formats in a ZIP file",
                    use_container_width=True
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

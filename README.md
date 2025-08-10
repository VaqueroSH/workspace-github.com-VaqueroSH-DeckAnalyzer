# MTG Deck Analyzer 🃏

A Python program and Streamlit web app that analyzes Magic: The Gathering decklists and provides comprehensive statistics using the Scryfall API.

## Features ✨

- **Total card counts** - Total cards and unique cards in the deck
- **Land analysis** - Counts and percentages of lands vs nonlands
- **Color distribution** - Interactive pie chart showing which colors appear in your deck and how often
- **Mana curve analysis** - Average mana value and distribution across mana costs
- **Visual mana curve** - Interactive bar chart showing your deck's curve
- **Missing card detection** - Reports any cards that couldn't be found
- **Rarity breakdown** - Detailed rarity statistics
- **Most expensive cards** - Highlights the priciest cards in your deck

## Installation 🚀

1. **Clone or download** this repository
2. **Install dependencies**:
   ```bash
   python3 -m pip install -r requirements.txt
   ```

That's it! The program uses the free Scryfall API (no API key required).

## Usage 📋

### Command-Line Interface
```bash
python3 main.py your_decklist.txt
```

### Streamlit Web App
Run the following command to start the web app:
```bash
streamlit run streamlit_app.py
```

### Example Output

```
============================================================
🃏 DECK ANALYSIS RESULTS
============================================================

📊 BASIC STATISTICS
   Total cards: 105
   Unique cards: 82
   Lands: 33 (31.4%)
   Nonlands: 72 (68.6%)

🎨 COLOR DISTRIBUTION
   Black (B): 58 cards (70.7%)

📈 MANA CURVE (Nonlands only)
   Average mana value: 2.74
   Distribution:
      0 CMC:  1
      1 CMC: 13
      2 CMC: 18
      3 CMC: 24
      4 CMC:  9
      5 CMC:  3
      6 CMC:  3
      7+ CMC:  1

   Interactive bar chart:
   - Displays mana curve distribution visually.
   - Groups 7+ CMC cards together for cleaner display.
   - Provides hover tooltips for detailed card counts.

============================================================
✅ Analysis complete! Successfully analyzed 100.0% of cards.
```

## Supported Decklist Formats 📝

The analyzer supports common decklist formats:

### Standard Format
```
1 Lightning Bolt
4 Mountain  
24 Swamp
1 Sol Ring
```

### Alternative Format
```
4x Lightning Bolt
1x Sol Ring
```

### Simple Format
```
Lightning Bolt
Sol Ring
Mountain
Mountain
Mountain
Mountain
```

## File Structure 📁

```
workspace-github.com-VaqueroSH-DeckAnalyzer-1/
├── main.py           # Command-line interface
├── streamlit_app.py  # Streamlit web app
├── scryfall_api.py   # Scryfall API client
├── deck_parser.py    # Decklist parsing
├── models.py         # Data models and analyzer
├── requirements.txt  # Dependencies
└── README.md         # This file
```

## How It Works 🔧

1. **Parse** your decklist file to extract card names and quantities
2. **Fetch** card information from the Scryfall API (colors, mana cost, type, etc.)
3. **Calculate** statistics including mana curve, color distribution, land ratios
4. **Display** results in a formatted report or interactive visualizations

## Features in Detail 📊

### Basic Statistics
- Total number of cards in the deck
- Number of unique cards (excluding duplicates)
- Land vs nonland breakdown with percentages

### Color Analysis
- Counts how many cards contain each color
- Shows percentages of your deck's color distribution
- Handles colorless cards appropriately

### Mana Curve
- Calculates average mana value for nonland cards
- Shows distribution across all mana costs
- Interactive bar chart for quick analysis
- Groups 7+ CMC cards together for cleaner display

### Error Handling
- Reports cards that couldn't be found in the database
- Handles network errors gracefully
- Provides helpful error messages

## Streamlit Visualizations 🌐

The Streamlit web app provides:
- **Interactive color pie chart** for color distribution
- **Interactive mana curve bar chart** for mana cost analysis
- **Detailed rarity breakdown**
- **Most expensive cards** table
- **Card type distribution** horizontal bar chart

## Rate Limiting ⚡

The program automatically rate-limits API requests to stay within Scryfall's limits (5 requests/second). For most decks, analysis completes in 15-20 seconds.

## Requirements 🐍

- Python 3.7+
- `requests` library (automatically installed)
- `streamlit` library (automatically installed)

## Example Deck Analysis 🎯

Your Sephiroth Commander deck analysis showed:
- **105 total cards** with 82 unique cards
- **Well-balanced mana curve** averaging 2.74 CMC
- **Mono-black identity** with 58 black cards (70.7%)
- **Good land ratio** at 31.4% lands
- **Perfect data coverage** - 100% of cards found!

## Contributing 🤝

Feel free to submit issues or improvements! The codebase is modular and easy to extend.

## FAQ ❓

**Q: Does this work with Commander decks?**  
A: Yes! It supports any deck size, including 100-card Commander decks.

**Q: Can I analyze decks without internet?**  
A: No. The app requires an internet connection to fetch card data from Scryfall.

**Q: Is my data stored anywhere?**  
A: No. All analysis happens locally; no deck data is uploaded or stored.

**Q: What about double-faced cards?**  
A: Fully supported. The analyzer handles transform cards, modal double-faced cards (MDFCs), split/fuse, and adventure cards.

## License 📄

This project uses the free Scryfall API and respects their terms of service. Card data and images are property of Wizards of the Coast.

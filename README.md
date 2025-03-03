# TT2 Alchemy Event Visual Optimizer

This application helps optimize ingredients for the Tap Titans 2 Alchemy Event using linear programming and provides a visual interface with Streamlit.

## Features

- Visual representation of alchemy ingredients using images
- Optimization of ingredient combinations to maximize rewards
- Customizable importance scores for different reward types
- Beautifully formatted result cards showing combinations

## Project Structure

The project is organized into multiple files for better maintainability:

- `main.py` - Main application entry point
- `utils.py` - Utility functions for HTML rendering and data extraction
- `config.py` - Configuration settings like ingredient images and default scores
- `components.py` - UI components for rendering inputs and results
- `optimiser.py` - Linear programming optimization functions
- `requirements.txt` - Required Python packages

## Installation

1. Make sure you have Python 3.8+ installed
2. Install required packages:

```bash
pip install -r requirements.txt
```

## Usage

1. Place your `TT2 Alchemy Event.csv` file in the same directory as the scripts
2. Run the application:

```bash
streamlit run main.py
```

3. Adjust ingredient counts and importance scores as needed
4. Click "Optimize" to get the best combinations

## CSV Format Requirements

The CSV file should have the following format:
- First column: Names of ingredients (rows and index)
- Other cells: Result of combining row ingredient with column ingredient

For example:
```
          Leaf   Sand  Water
Leaf      Leaf   Sand  Mushroom
Sand      Sand   Sand  Berries
Water     Mushroom Berries Water
```

## Customization

- Update ingredient images in `config.py`
- Modify the UI styling in `utils.py`
- Add new loot types in the default importance scores in `config.py`

## License

MIT

## Credits

Created for Tap Titans 2 players to optimize their Alchemy Event rewards.
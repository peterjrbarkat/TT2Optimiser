## TT2 Alchemy Event Optimizer

Optimize your Tap Titans 2 Alchemy Event brews with a one-click Streamlit app that solves the best set of combinations given:
- Your current ingredient counts
- Your personal valuation of rewards (importance scores)

The optimizer models the event as an integer linear program (via PuLP) and produces:
- A ranked list of brews to craft
- Total loot and a weighted score
- A step-by-step inventory tracker with highlights
- An optional graph view to visualize transitions


### Features
- Editable source data: tweak the CSV directly in-app
- Auto-read ingredient counts from a screenshot (optional Google API key)
- User-adjustable importance scores to reflect your preferences
- Optimal solution via linear programming
- Inventory change tracker with visual diffs
- Experimental graph visualization of brew transitions


### Project layout
- `streamlit_app.py`: Main Streamlit UI and optimization pipeline
- `TT2 Alchemy Event.csv`: Base combinations and rewards
- `src/`
  - `genai_client.py`: Calls Google GenAI to parse ingredient counts from a screenshot
  - `inventory_tracking.py`: Inventory history + change highlighting
  - `graph_visualisation.py`: Experimental transitions visual
  - `render_combo.py`: Result rendering utilities
  - `config.py`: Loads ingredient images
- `imgs/`: Ingredient icons


### Quickstart
1) Install Python 3.10+ (recommended).
2) Install dependencies:

```bash
pip install -r requirements.txt
```

3) Run the app:

```bash
streamlit run streamlit_app.py
```

4) Open the URL printed by Streamlit (usually `http://localhost:8501`).


### Optional: enable screenshot-to-counts
If you want the app to auto-read ingredient counts from a screenshot of your alchemy screen, provide a Google API key for the `google-genai` client.

- Preferred (Streamlit secrets): create `.streamlit/secrets.toml` at the project root:

```toml
GOOGLE_CLOUD_API_KEY = "YOUR_API_KEY"
```

- Or set an environment variable before starting Streamlit:
  - PowerShell (Windows):
    ```powershell
    $env:GOOGLE_CLOUD_API_KEY="YOUR_API_KEY"
    streamlit run streamlit_app.py
    ```
  - macOS/Linux:
    ```bash
    export GOOGLE_CLOUD_API_KEY="YOUR_API_KEY"
    streamlit run streamlit_app.py
    ```

This enables the “Upload a screenshot” flow in the “Number of Ingredients” section.


### How to use the app
1) Edit CSV (optional)
   - Expand “Edit CSV Data” to view or tweak the data from `TT2 Alchemy Event.csv`. Changes are applied immediately to the optimization.

2) Enter ingredient counts
   - Either upload a lab screenshot to auto-extract counts (with API key set) or edit the counts table directly.

3) Set importance scores
   - In “Importance Scores”, set your weights for each loot type (e.g., “how many gems I’d pay for this reward”). This drives the optimizer’s objective.

4) Review results
   - The app computes an optimal set of brews and shows:
     - Total weighted score and loot totals
     - The craft list with images (if available) and outputs
     - “Check brews” table: a step-by-step inventory view with changes highlighted
     - “Visualise results (Experimental)”: a graph-style overview of transitions


### Under the hood (very brief)
- The app builds an integer linear program with PuLP:
  - Decision variables: integer counts per brew combination
  - Objective: maximize sum of (importance × loot amount × brew count)
  - Constraints: ingredient usage must not exceed available stock (factoring in intermediate ingredient creation)


### Troubleshooting
- Import errors for `config`, `inventory_tracking`, etc.:
  - Run the app from the project root: `streamlit run streamlit_app.py`
  - If your environment doesn’t find modules in `src/`, you can set `PYTHONPATH` to include it.
    - PowerShell:
      ```powershell
      $env:PYTHONPATH = "$PWD\src"
      streamlit run streamlit_app.py
      ```
    - macOS/Linux:
      ```bash
      export PYTHONPATH="$PWD/src"
      streamlit run streamlit_app.py
      ```

- Ingredient images not showing:
  - Ensure all PNGs exist under `imgs/` and that the loader in `src/config.py` points to the correct folder location in your environment.

- Graph visualization:
  - The app uses the `graphviz` Python package. If rendering issues occur, install Graphviz system binaries for your OS or run without the experimental graph.

- Google GenAI errors:
  - Make sure `google-genai` is installed (covered by `requirements.txt`) and a valid `GOOGLE_CLOUD_API_KEY` is set. The feature is optional; the app works without it.


### Development
- Python formatting/style is conventional; contributions welcome.
- Keep `TT2 Alchemy Event.csv` tidy—column/index names drive parsing and optimization.


### License
This project is licensed under the terms of the MIT License. See `LICENSE` for details.

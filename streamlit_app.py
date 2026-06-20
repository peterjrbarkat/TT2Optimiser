import streamlit as st
import pandas as pd
from pulp import LpMaximize, LpProblem, LpVariable, lpSum, value
from src.config import get_ingredient_images
from src.graph_visualisation import render_graph_visualization
from src.inventory_tracking import track_inventory_from_formatted_combos
from src.inventory_tracking import highlight_changes
import os
import hashlib
from src.genai_client import extract_counts_from_image
from src.render_combo import render_results

ingredient_images = get_ingredient_images()

# Load the CSV file
file_path = 'TT2 Alchemy Event.csv'
df = pd.read_csv(file_path, index_col=0)

# Combined function to extract loot (including currency and handling specific keywords)
def extract_loot(value, importance_keys):
    if isinstance(value, str):
        parts = value.split()
        try:
            amount = int(parts[0])
            item_type = ' '.join(parts[1:])
            for key in importance_keys:
                if key in item_type:
                    return (key, amount)
            return (item_type, amount)
        except (ValueError, IndexError):
            pass
    return ('Unknown', 0)

# Default importance scores
default_importance_scores = {
    "Currency": 100,
    "Crafting Shards": 1,
    "Perk Tickets": 1,
    "Skill Points": 1,
    "Eggs": 1,
    "Raid Cards": 1,
    "Wildcards": 1,
    "Common Equipment": 1,
    "Rare Equipment": 1,
    "Legendary Equipment": 1,
    "Event Equipment": 1,
    "Clan Scroll": 1,
    "Fortune Scroll": 1,
    "Fortune Weapons": 1,
    "Hero Weapons": 1
}

# Apply the function to the dataframe
loot_df = df.applymap(lambda x: extract_loot(x, default_importance_scores.keys()))

# Extracting relevant data for optimization
items = list(df.index)
combinations = [(i, j) for i in items for j in items if i <= j]

# Streamlit inputs
st.set_page_config(layout="wide")
st.title("TT2 Alchemy Event Optimizer")

st.success("Updated for June 2026 Event! For any feedback or bugs, please reach out to peterbarkat@gmail.com")
st.info('If the app is running slowly, try these alternative links: [V2](https://tt2optimiser-v2.streamlit.app/), [V3](https://tt2optimiser-v3.streamlit.app/), [V4](https://tt2optimiser-v4.streamlit.app/), [V5](https://tt2optimiser-v5.streamlit.app/).')

# Editable dataframe for the CSV data
with st.expander("Edit CSV Data", expanded=False):
    edited_df = st.data_editor(df)

# Create input columns for the number of ingredients and the importance
st.header("Input the number of ingredients and importance scores:")

col1, col2 = st.columns(2)

ingredient_counts = {}
importance_scores = {}

with col1:
    st.subheader("Number of Ingredients")
    uploaded_file = st.file_uploader("Upload a screenshot of alchemy lab to auto-extract ingredient counts", type=["jpg", "jpeg", "png"])

    # Resolve API key with secrets-first priority; if none, allow input
    api_key_from_secrets = None
    try:
        if hasattr(st, "secrets") and "GOOGLE_CLOUD_API_KEY" in st.secrets:
            api_key_from_secrets = st.secrets["GOOGLE_CLOUD_API_KEY"]
    except Exception:
        api_key_from_secrets = None
    api_key_from_env = os.environ.get("GOOGLE_CLOUD_API_KEY")
    effective_api_key = api_key_from_secrets or api_key_from_env

    if uploaded_file is not None and effective_api_key:
        # Use full bytes value and hash to avoid re-calling model on reruns
        image_bytes = uploaded_file.getvalue()
        mime_type = uploaded_file.type or "image/jpeg"
        image_hash = hashlib.sha256(image_bytes).hexdigest()

        # Only call the Google model when a new image is uploaded
        if st.session_state.get("last_uploaded_image_hash") != image_hash or "extracted_counts" not in st.session_state:
            with st.spinner("Calling Google model..."):
                raw_text, counts_dict = extract_counts_from_image(
                    image_bytes=image_bytes,
                    mime_type=mime_type,
                    ingredient_names=list(df.index),
                    api_key=effective_api_key,
                )
            if counts_dict:
                st.session_state["extracted_counts"] = counts_dict
                st.session_state["last_uploaded_image_hash"] = image_hash

        # Show parsed dictionary if available (without re-calling the model)
        # if st.session_state.get("extracted_counts"):
            # st.subheader("Parsed dictionary (applied below)")
            # st.json(st.session_state["extracted_counts"])
    elif uploaded_file is not None and not effective_api_key:
        st.warning("No API key found. Add it to Streamlit secrets or enter above.")
    ingredient_data = pd.DataFrame({
        "Ingredient": items,
        "Count": [
            (st.session_state.get("extracted_counts", {}).get(name, 2)) for name in items
        ]
    })
    edited_ingredient_data = st.data_editor(ingredient_data, num_rows="fixed", use_container_width=True, hide_index=True)
    for index, row in edited_ingredient_data.iterrows():
        ingredient_counts[row["Ingredient"]] = int(row["Count"])

    print(ingredient_counts)

with col2:
    st.subheader("Importance Scores")
    st.caption("Tip: You can set 'importance' to the number of gems you'd pay for each loot type to compare rewards fairly.")
    importance_data = pd.DataFrame({
        "Loot Type": list(default_importance_scores.keys()),
        "Importance": list(default_importance_scores.values())
    })
    # make "Importance" a float
    importance_data["Importance"] = importance_data["Importance"].astype(float)

    edited_importance_data = st.data_editor(importance_data, num_rows="fixed", use_container_width=True, hide_index=True)
    for index, row in edited_importance_data.iterrows():
        importance_scores[row["Loot Type"]] = float(row["Importance"])

st.divider()
if st.button("Run optimizer", type="primary"):
    prob = LpProblem("Maximize Loot Score", LpMaximize)

    combo_vars = LpVariable.dicts("Combo", combinations, lowBound=0, cat='Integer')

    prob += lpSum([
        importance_scores.get(extract_loot(df.loc[combo], importance_scores.keys())[0], 0) * extract_loot(df.loc[combo], importance_scores.keys())[1] * combo_vars[combo]
        for combo in combinations
    ])

    for item in items:
        used = lpSum([combo_vars[combo] for combo in combinations if combo[0] == item]) + \
               lpSum([combo_vars[combo] for combo in combinations if combo[1] == item])
        created = lpSum([combo_vars[combo] for combo in combinations if df.loc[combo] == item])
        prob += used <= ingredient_counts[item] + created

    prob.solve()

    combos_used = [(combo, value(var), df.loc[combo]) for combo, var in combo_vars.items() if value(var) > 0]

    total_loot = {}
    formatted_combos = []
    total_score = 0

    combos_used = sorted(combos_used, key=lambda x: items.index(x[0][0]))
    combos_used = sorted(combos_used, key=lambda x: any(key in x[2] for key in importance_scores.keys()))

    for combo, count, product in combos_used:
        product_name, product_amount = extract_loot(product, importance_scores.keys())
        if product_name in total_loot:
            total_loot[product_name] += product_amount * count
        else:
            total_loot[product_name] = product_amount * count
        total_score += importance_scores.get(product_name, 0) * product_amount * count
        formatted_combos.append({
            'input1': combo[0],
            'input2': combo[1],
            'count': count,
            'result': product,
            'is_ingredient': not any(key in product for key in importance_scores.keys() if isinstance(product, str))
        })

    st.session_state["optimization_output"] = {
        "total_score": total_score,
        "combos_used": combos_used,
        "total_loot": total_loot,
        "formatted_combos": formatted_combos,
        "ingredient_counts": dict(ingredient_counts),
    }

if "optimization_output" not in st.session_state:
    st.info("Set your ingredients and importance scores, then click **Run optimizer** to see results.")
else:
    o = st.session_state["optimization_output"]
    render_results(o["total_score"], o["combos_used"], o["total_loot"], ingredient_images)

    st.subheader("Check brews:")
    st.write("Changes in the quantities are highlighted in yellow")
    df = track_inventory_from_formatted_combos(o["ingredient_counts"], o["formatted_combos"])

    styled_df = highlight_changes(df)
    st.write(styled_df)

    with st.expander("Visualise results - (Experimental)", expanded=False):
        render_graph_visualization(
            o["combos_used"], o["ingredient_counts"], o["total_loot"], o["formatted_combos"]
        )

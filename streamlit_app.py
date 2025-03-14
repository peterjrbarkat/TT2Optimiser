import streamlit as st
import pandas as pd
from components import render_results, render_ingredient_input, render_importance_input
from pulp import LpMaximize, LpProblem, LpVariable, lpSum, value
from config import get_ingredient_images, get_default_importance_scores
from graph_visualisation import render_graph_visualization
from inventory_tracking import track_inventory_from_formatted_combos, create_transition_df_from_inventory

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
    "Shards": 1,
    "Perks": 1,
    "Raid Cards": 1,
    "Common Equipment": 1,
    "Rare Equipment": 1,
    "Event Equipment": 1,
    "Dust": 1,
    "Skill Points": 1,
    "Pet Eggs": 1,
    "Clan Eggs": 1,
    "Wildcards": 1,
    "Clan Scrolls": 1,
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
    ingredient_data = pd.DataFrame({
        "Ingredient": items,
        "Count": [2] * len(items)
    })
    edited_ingredient_data = st.data_editor(ingredient_data, num_rows="fixed", use_container_width=True, hide_index=True)
    for index, row in edited_ingredient_data.iterrows():
        ingredient_counts[row["Ingredient"]] = int(row["Count"])

with col2:
    st.subheader("Importance Scores")
    importance_data = pd.DataFrame({
        "Loot Type": list(default_importance_scores.keys()),
        "Importance": list(default_importance_scores.values())
    })
    # make "Importance" a float
    importance_data["Importance"] = importance_data["Importance"].astype(float)

    edited_importance_data = st.data_editor(importance_data, num_rows="fixed", use_container_width=True, hide_index=True)
    for index, row in edited_importance_data.iterrows():
        importance_scores[row["Loot Type"]] = float(row["Importance"])

# Button to trigger the optimization
if st.button("Optimize"):

    # Create a new LP problem
    prob = LpProblem("Maximize Loot Score", LpMaximize)

    # Define variables
    combo_vars = LpVariable.dicts("Combo", combinations, lowBound=0, cat='Integer')

    # Objective function: sum of (importance score * loot amount * variable) for each combination
    prob += lpSum([
        importance_scores.get(extract_loot(df.loc[combo], importance_scores.keys())[0], 0) * extract_loot(df.loc[combo], importance_scores.keys())[1] * combo_vars[combo]
        for combo in combinations
    ])

    # Constraints for each item
    for item in items:
        # Used items constraints
        used = lpSum([combo_vars[combo] for combo in combinations if combo[0] == item]) + \
               lpSum([combo_vars[combo] for combo in combinations if combo[1] == item])

        # Created items constraints
        created = lpSum([combo_vars[combo] for combo in combinations if df.loc[combo] == item])

        prob += used <= ingredient_counts[item] + created

    # Solve the problem
    prob.solve()

    # Extract results
    combos_used = [(combo, value(var), df.loc[combo]) for combo, var in combo_vars.items() if value(var) > 0]

    # Calculate total loot and score
    total_loot = {}
    formatted_combos = []
    total_score = 0

    # and then order the ouput by the order of the items
    combos_used = sorted(combos_used, key=lambda x: items.index(x[0][0]))

    # reorder the combos_used to have the ingredients first
    combos_used = sorted(combos_used, key=lambda x: any(key in x[2] for key in importance_scores.keys()))

    # st.write(combos_used)

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

    # st.header("Results")
    # st.write(f"Maximum score: {total_score}")

    # st.write(combos_used)
    from render_combo import render_results
    render_results(total_score, combos_used, total_loot, ingredient_images)

    with st.expander("Check inventory over time", expanded=False):
        for combo, count, product in combos_used:
            product_name, product_amount = extract_loot(product, importance_scores.keys())
            st.write(f"{count} x {combo} = {product}")

        st.write(track_inventory_from_formatted_combos(ingredient_counts, formatted_combos))

    st.subheader("Total loot obtained:")
    for loot, amount in total_loot.items():
        st.write(f"{loot}: {amount}")

    # graph visualisation
    inventory_df = render_graph_visualization(combos_used, ingredient_counts, total_loot, formatted_combos)
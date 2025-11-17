import streamlit as st
import graphviz
import re
import pandas as pd

def track_inventory_from_formatted_combos(ingredient_counts, formatted_combos):
    """
    Track inventory changes using the formatted combo data from the optimizer.

    Args:
        ingredient_counts (dict): Dictionary of initial ingredient counts
        formatted_combos (list): List of dicts with keys: input1, input2, count, result, is_ingredient

    Returns:
        pandas.DataFrame: DataFrame tracking inventory at each step
    """
    import pandas as pd
    from collections import defaultdict

    # Initialize history with initial state
    history = [{"Step": "Initial", "Action": "-", **ingredient_counts}]

    # Start with initial inventory
    current_inventory = ingredient_counts.copy()
    seen_values = defaultdict(list)

    # Initialize seen values tracking
    for item, count in current_inventory.items():
        seen_values[item].append(count)

    # Sort formatted_combos: ingredient-producing first, then loot-producing
    sorted_combos = sorted(formatted_combos, key=lambda x: not x['is_ingredient'])

    # Process each combination
    for i, combo in enumerate(sorted_combos, 1):
        # Create a copy of the current inventory
        new_inventory = current_inventory.copy()

        # Extract combo data
        input1, input2 = combo['input1'], combo['input2']
        count, result = combo['count'], combo['result']
        is_ingredient = combo['is_ingredient']

        # Format action string
        action = f"{count} x ('{input1}', '{input2}') = {result}"

        # Update inputs (decrease used ingredients)
        new_inventory[input1] = max(0, new_inventory.get(input1, 0) - count)
        new_inventory[input2] = max(0, new_inventory.get(input2, 0) - count)

        # Handle the result
        if is_ingredient:
            # It's an ingredient - add to inventory with unique value if needed
            if result in new_inventory:
                new_value = new_inventory[result] + count

                # Ensure uniqueness by adding a small increment if needed
                if new_value in seen_values[result]:
                    new_value += 0.001

                new_inventory[result] = new_value
                seen_values[result].append(new_value)
            else:
                new_inventory[result] = count
                seen_values[result].append(count)
        else:
            # It's a loot/currency item
            # Extract amount and loot type
            loot_match = re.match(r"(\d+)\s*(.+)", result)
            if loot_match:
                amount = int(loot_match.group(1))
                loot_type = loot_match.group(2)

                # Increase loot count
                new_inventory[loot_type] = new_inventory.get(loot_type, 0) + amount * count

        # Add step to history
        history.append({"Step": f"Step {i}", "Action": action, **new_inventory})

        # Update current inventory for next iteration
        current_inventory = new_inventory

    # Convert to DataFrame
    df = pd.DataFrame(history).fillna(0)

    # Reorder columns to have Step and Action first
    cols = ["Step", "Action"] + [c for c in df.columns if c not in ["Step", "Action"]]
    return df[cols]


def create_transition_df_from_inventory(inventory_df):
    """
    Create a transition DataFrame from inventory history.

    Args:
        inventory_df (pandas.DataFrame): DataFrame with inventory history

    Returns:
        pandas.DataFrame: Transition DataFrame for visualization
    """
    import pandas as pd

    transitions = []

    # Iterate through steps (skip the first/initial state)
    for i in range(1, len(inventory_df)):
        # Get states
        before_state = inventory_df.iloc[i - 1].to_dict()
        after_state = inventory_df.iloc[i].to_dict()
        action = after_state['Action']

        # Parse action
        action_match = re.match(r"([\d.]+)\s*x\s*\('([^']+)',\s*'([^']+)'\)\s*=\s*(.+)", action)

        if action_match:
            count, input1, input2, result = action_match.groups()

            # Format count display (integer if possible)
            def format_count(value):
                return str(int(value)) if value == int(value) else str(value)

            # Format inputs with counts
            input1_before = f"{input1} ({format_count(before_state.get(input1, 0))})"
            input2_before = f"{input2} ({format_count(before_state.get(input2, 0))})"

            # Format outputs
            loot_match = re.match(r"(\d+)\s*(.+)", result)
            if loot_match and loot_match.group(2) != result:
                # It's loot/currency
                loot_type = loot_match.group(2)
                output1 = f"{loot_type} ({format_count(after_state.get(loot_type, 0))})"
            else:
                # It's an ingredient
                result_item = result.strip()
                output1 = f"{result_item} ({format_count(after_state.get(result_item, 0))})"

            # Format ingredient updates
            output2 = f"{input1} ({format_count(after_state.get(input1, 0))})"
            output3 = f"{input2} ({format_count(after_state.get(input2, 0))})"

            # Add transition row
            transitions.append({
                'input1': input1_before,
                'input2': input2_before,
                'action': action,
                'output1': output1,
                'output2': output2,
                'output3': output3
            })

    return pd.DataFrame(transitions)


def highlight_changes(df):
    """
    Highlight cells where values differ from the previous row.
    - Skip highlighting the first row entirely
    - Skip highlighting the first two columns
    - Use pale yellow (#FFFFCC) for highlighting
    - Round all values to the nearest integer
    Returns a styled pandas DataFrame.
    """
    # Create a copy and round all numeric values to the nearest integer
    rounded_df = df.copy()
    for col in rounded_df.columns:
        # Check if the column contains numeric values
        if pd.api.types.is_numeric_dtype(rounded_df[col]):
            rounded_df[col] = rounded_df[col].round(0).astype(int)

    # Define a styling function to highlight changes
    def style_changed_cells(x):
        # Create an empty DataFrame with the same shape as the input
        highlighted = pd.DataFrame('', index=x.index, columns=x.columns)

        # For each column (skipping the first two columns)
        for col in x.columns[2:]:
            # Create a mask where values differ from previous row
            mask = x[col].ne(x[col].shift())

            # Skip the first row
            mask.iloc[0] = False

            # Set the style for cells where values changed
            highlighted.loc[mask, col] = 'background-color: #FFFFCC'

        return highlighted

    # for the df column replace ' x ' with ' x [' and add ] at the end just for the Action column
    rounded_df['Action'] = rounded_df['Action'].str.replace(' x ', ' x [') + ']'
    # replace . with a +
    rounded_df['Action'] = rounded_df['Action'].str.replace(',', ' +')
    rounded_df['Action'] = rounded_df['Action'].str.replace("'", '')
    rounded_df['Action'] = rounded_df['Action'].str.replace(")", '')
    rounded_df['Action'] = rounded_df['Action'].str.replace("(", '')

    # put the first action value to ""
    rounded_df['Action'].iloc[0] = ""

    # reorder the columns so that the columns after Scale are put after Action
    columns = list(rounded_df.columns)
    columns = columns[:2] + columns[columns.index('Scale')+1:] + columns[2:columns.index('Scale')]
    rounded_df = rounded_df[columns]

    # drop the step column
    # rounded_df = rounded_df.drop(columns=['Step'])

    # Apply the styling function
    return rounded_df.style.apply(style_changed_cells, axis=None)
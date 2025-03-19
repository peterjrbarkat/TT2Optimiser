import streamlit as st
import pandas as pd
import re
from utils import get_img_html, extract_loot

def render_combination_card(combo, count, product, ingredient_images):
    """Render a card for a single alchemy combination

    Args:
        combo (tuple): Tuple of ingredient names
        count (float): Number of times this combination is used
        product (str): The product of the combination
        ingredient_images (dict): Dictionary mapping ingredient names to image URLs
    """
    # Check if it's a product with amount (like Currency)
    if isinstance(product, str) and re.match(r'^\d+\s+', product):
        amount_match = re.match(r'^(\d+)\s+(.+)$', product)
        if amount_match:
            amount, type_name = amount_match.groups()
            result_html = f'<span class="count-badge">{int(count)}x [</span>'

            # First ingredient
            result_html += f'<img src="{ingredient_images.get(combo[0], "")}" width="40" height="40" class="ingredient-img"/>'

            # Plus sign
            result_html += '<span class="plus-sign">+</span>'

            # Second ingredient
            result_html += f'<img src="{ingredient_images.get(combo[1], "")}" width="40" height="40" class="ingredient-img"/>'

            # Equals sign
            result_html += '<span class="equals-sign">=</span>'

            # Result
            if "Currency" in type_name:
                result_html += f'<span class="currency">{amount} {type_name}</span>'
            else:
                result_html += f'{amount} {type_name}'

            result_html += '<span class="equals-sign"> ]</span>'

            st.markdown(f'<div class="result-card">{result_html}</div>', unsafe_allow_html=True)
    else:
        # It's an ingredient product
        result_html = f'<span class="count-badge">{int(count)}x [</span>'

        # First ingredient
        result_html += f'<img src="{ingredient_images.get(combo[0], "")}" width="40" height="40" class="ingredient-img"/>'

        # Plus sign
        result_html += '<span class="plus-sign">+</span>'

        # Second ingredient
        result_html += f'<img src="{ingredient_images.get(combo[1], "")}" width="40" height="40" class="ingredient-img"/>'

        # Equals sign
        result_html += '<span class="equals-sign">=</span>'

        # Result ingredient
        if product in ingredient_images:
            result_html += f'<img src="{ingredient_images.get(product, "")}" width="40" height="40" class="ingredient-img"/> {product}'
        else:
            result_html += product

        result_html += '<span class="equals-sign"> ]</span>'

        st.markdown(f'<div class="result-card">{result_html}</div>', unsafe_allow_html=True)



def render_results(total_score, combos_used, total_loot, ingredient_images, num_columns=4):
    """Render the results section with combinations displayed in customizable columns

    Args:
        total_score (float): The total score from optimization
        combos_used (list): List of tuples (combo, count, product)
        total_loot (dict): Dictionary of total loot by type
        ingredient_images (dict): Dictionary mapping ingredient names to image URLs
        num_columns (int, optional): Number of columns to display results in. Defaults to 4.
    """

    # Allow user to select number of columns
    selected_columns = 3

    # Render total loot
    st.markdown('<div class="total-container">', unsafe_allow_html=True)
    st.subheader("Total loot obtained:")
    st.write(f"Maximum score: {int(total_score)}")

    # Display loot in columns too if there are multiple loot types
    if len(total_loot) > selected_columns:
        loot_cols = st.columns(selected_columns)
        for i, (loot, amount) in enumerate(total_loot.items()):
            col_idx = i % selected_columns
            with loot_cols[col_idx]:
                if loot == "Currency":
                    st.markdown(f'<p><span class="currency">{loot}</span>: <b>{int(amount)}</b></p>',
                                unsafe_allow_html=True)
                else:
                    st.markdown(f'<p>{loot}: <b>{int(amount)}</b></p>', unsafe_allow_html=True)
    else:
        # If just a few loot types, show them in a single row
        for loot, amount in total_loot.items():
            if loot == "Currency":
                st.markdown(f'<p><span class="currency">{loot}</span>: <b>{int(amount)}</b></p>',
                            unsafe_allow_html=True)
            else:
                st.markdown(f'<p>{loot}: <b>{int(amount)}</b></p>', unsafe_allow_html=True)

    st.subheader("Combinations used:")

    # Split combinations across selected number of columns
    total_combos = len(combos_used)
    combos_per_column = (total_combos + selected_columns - 1) // selected_columns  # Ceiling division

    # Create the columns
    cols = st.columns(selected_columns)

    # Distribute combinations across columns
    for i, (combo, count, product) in enumerate(combos_used):
        column_index = i // combos_per_column
        if column_index >= selected_columns:  # Ensure we don't exceed our columns
            column_index = selected_columns - 1

        # Render the combination in the appropriate column
        with cols[column_index]:
            render_combination_card(combo, count, product, ingredient_images)

    st.markdown('</div>', unsafe_allow_html=True)
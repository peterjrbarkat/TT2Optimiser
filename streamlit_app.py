import streamlit as st
import pandas as pd
from pulp import LpMaximize, LpProblem, LpVariable, lpSum, value

# Import helper modules
from utils import set_custom_styles, get_img_html, extract_loot
from config import get_ingredient_images, get_default_importance_scores
from components import render_results, render_ingredient_input, render_importance_input
from optimiser import create_and_solve_lp_problem
from graph_visualisation import render_graph_visualization


def main():
    """Main function to run the Streamlit application"""
    # Set page configuration
    st.set_page_config(layout="wide", page_title="TT2 Alchemy Visual Optimizer")

    # Apply custom styles
    set_custom_styles()

    # App title and description
    st.title("TT2 Alchemy Event Visual Optimizer")
    st.markdown("""
    This application helps you optimize your ingredients for the Tap Titans 2 Alchemy Event.
    Input your available ingredients and set importance values for different rewards, then click "Optimize".
    """)

    try:
        # Load the CSV file
        try:
            file_path = 'TT2 Alchemy Event.csv'
            df = pd.read_csv(file_path, index_col=0)
            st.success(f"Successfully loaded {file_path}")
        except Exception as e:
            st.error(f"Error loading CSV file: {str(e)}")
            st.info("Please make sure 'TT2 Alchemy Event.csv' is in the same directory as this script.")
            st.stop()

        # Get default configuration
        ingredient_images = get_ingredient_images()
        default_importance_scores = get_default_importance_scores()

        # Editable dataframe for the CSV data
        with st.expander("Edit CSV Data", expanded=False):
            edited_df = st.data_editor(df)
            if edited_df is not None:
                df = edited_df

        # Create input columns for the number of ingredients and the importance
        st.header("Input the number of ingredients and importance scores:")

        col1, col2 = st.columns(2)

        # Extracting relevant data for optimization
        items = list(df.index)

        # Render ingredient inputs
        with col1:
            ingredient_counts = render_ingredient_input(items, ingredient_images)

        # Render importance score inputs
        with col2:
            importance_scores = render_importance_input(default_importance_scores)

        # Button to trigger the optimization
        if st.button("Optimize", type="primary"):
            with st.spinner("Calculating optimal combinations..."):
                # Create combinations from items
                combinations = [(i, j) for i in items for j in items if i <= j]

                # Solve the optimization problem
                # Note: Updated to handle the fourth return value (formatted_combos)
                total_score, combos_used, total_loot, formatted_combos = create_and_solve_lp_problem(
                    df,
                    combinations,
                    ingredient_counts,
                    importance_scores
                )

                # Render the results
                render_results(total_score, combos_used, total_loot, ingredient_images)

                # Add a divider
                st.markdown("---")

                # Display the crafting flow visualization
                st.header("Crafting Flow Visualization")
                st.markdown("This visualization shows how ingredients are combined to produce the optimal results.")

                # We'll use a full-width container for better visibility
                # Pass formatted_combos to the graph visualization function
                render_graph_visualization(combos_used, ingredient_counts, total_loot, formatted_combos)

                # Add a spacer
                st.markdown("<br><br>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.error("Please make sure the CSV file 'TT2 Alchemy Event.csv' is in the same directory as this script.")
        st.exception(e)  # Show detailed error information in development

    # Add footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #888;">
        <p>TT2 Alchemy Event Optimizer | Created for Tap Titans 2 players</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
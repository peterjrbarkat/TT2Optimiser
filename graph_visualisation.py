import streamlit as st
import graphviz
import re
from collections import defaultdict
from inventory_tracking import track_inventory_from_formatted_combos, create_transition_df_from_inventory


def create_crafting_visualization(transition_df, inventory_df):
    """
    Create a GraphViz visualization of the crafting system with linked nodes.
    - Ingredients are shown as squares
    - Actions are shown as triangles with count of operations
    - Outputs that aren't ingredients are shown as yellow squares
    - Links outputs to subsequent inputs when they're the same item
    - Adds final total nodes for outputs of the same type (e.g., Currency)
    """
    # Create a new directed graph
    dot = graphviz.Digraph(comment='Crafting System')

    # Set graph attributes for better width utilization and smaller boxes
    dot.attr(rankdir='TB')  # Top-to-Bottom
    dot.attr(nodesep='0.1')  # Reduce space between nodes on same rank
    dot.attr(ranksep='0.2')  # Reduce space between ranks
    dot.attr(ratio='fill')  # Fill the available space
    dot.attr(size='3,4')  # Set a larger size to spread out horizontally
    dot.attr(splines='polyline')  # Use straight lines for cleaner appearance

    # Set default node attributes for smaller sizes
    # dot.attr('node', fontsize='20', width='1.6', height='1.4', margin='0.05,0.02')

    # Get the final inventory (last row in inventory_df)
    final_inventory = inventory_df.iloc[-1].to_dict()

    # Track all unique ingredients to determine what's an ingredient vs. an output
    all_ingredients = set()

    # Track item nodes by name to reuse them
    item_nodes = {}  # Format: {item_name: node_id}

    # Track final values for each output type
    final_values = defaultdict(int)
    final_outputs = set()

    # First pass to collect all ingredients and final values
    for idx, row in transition_df.iterrows():
        # Extract ingredient names (without counts)
        input1_match = re.match(r'([A-Za-z]+)', row['input1'])
        input2_match = re.match(r'([A-Za-z]+)', row['input2'])

        if input1_match and input2_match:
            input1_name = input1_match.group(1)
            input2_name = input2_match.group(1)
            all_ingredients.add(input1_name)
            all_ingredients.add(input2_name)

        # Extract output name and count
        output1_match = re.match(r'([A-Za-z]+)(?:\s+\(([^)]+)\))?', row['output1'])
        if output1_match:
            if len(output1_match.groups()) > 1 and output1_match.group(2):
                output1_name, output1_count = output1_match.groups()
                try:
                    final_values[output1_name] = int(float(output1_count))
                except ValueError:
                    final_values[output1_name] = int(float(output1_count))
                final_outputs.add(output1_name)
            else:
                output1_name = output1_match.group(1)
                final_outputs.add(output1_name)
                final_values[output1_name] = 1

    # Second pass to create the graph
    for idx, row in transition_df.iterrows():
        # Create unique node IDs
        action_id = f"action_{idx}"

        # Extract ingredient names and counts
        input1_match = re.match(r'([A-Za-z]+)(?:\s+\(([^)]+)\))?', row['input1'])
        input2_match = re.match(r'([A-Za-z]+)(?:\s+\(([^)]+)\))?', row['input2'])
        output1_match = re.match(r'([A-Za-z]+)(?:\s+\(([^)]+)\))?', row['output1'])
        output2_match = re.match(r'([A-Za-z]+)(?:\s+\(([^)]+)\))?', row['output2'])
        output3_match = re.match(r'([A-Za-z]+)(?:\s+\(([^)]+)\))?', row['output3'])

        if input1_match and input2_match and output1_match:
            # Handle input1
            input1_name = input1_match.group(1)
            input1_count_raw = input1_match.group(2) if len(input1_match.groups()) > 1 and input1_match.group(
                2) else "1"
            input1_count_display = str(int(float(input1_count_raw)))

            # Handle input2
            input2_name = input2_match.group(1)
            input2_count_raw = input2_match.group(2) if len(input2_match.groups()) > 1 and input2_match.group(
                2) else "1"
            input2_count_display = str(int(float(input2_count_raw)))

            # Handle output1
            output1_name = output1_match.group(1)
            output1_count_raw = output1_match.group(2) if len(output1_match.groups()) > 1 and output1_match.group(
                2) else "1"
            output1_count_display = str(int(float(output1_count_raw)))

            # Create or get input node IDs - use raw values for IDs to maintain node positions
            input1_node_id = f"{input1_name}_{input1_count_raw}"
            if input1_node_id not in item_nodes:
                item_nodes[input1_node_id] = input1_node_id
                dot.node(input1_node_id, f"{input1_name}\n({input1_count_display})", shape='box')

            input2_node_id = f"{input2_name}_{input2_count_raw}"
            if input2_node_id not in item_nodes:
                item_nodes[input2_node_id] = input2_node_id
                dot.node(input2_node_id, f"{input2_name}\n({input2_count_display})", shape='box')

            # Extract the multiplier from the action
            action_multiplier_match = re.match(r'([\d.]+)\s*x', row['action'])
            action_multiplier = "x" + action_multiplier_match.group(1) if action_multiplier_match else ""

            # Add action node (triangle) with just the multiplier
            dot.node(action_id, action_multiplier, shape='triangle', fontsize='8')

            # Connect inputs to action
            dot.edge(item_nodes[input1_node_id], action_id)
            dot.edge(item_nodes[input2_node_id], action_id)

            # Process main output
            output1_node_id = f"{output1_name}_{output1_count_raw}"
            if output1_node_id not in item_nodes:
                item_nodes[output1_node_id] = output1_node_id
                if output1_name not in all_ingredients or output1_name in ['Currency', 'Shards', 'Perks', 'Dust',
                                                                           'Skill']:
                    dot.node(output1_node_id, f"{output1_name}\n({output1_count_display})",
                             shape='box', style='filled', fillcolor='yellow')
                else:
                    dot.node(output1_node_id, f"{output1_name}\n({output1_count_display})", shape='box')

            # Connect action to output
            dot.edge(action_id, item_nodes[output1_node_id])

            # Process output2 (updated count of input1)
            if output2_match:
                output2_name = output2_match.group(1)
                output2_count_raw = output2_match.group(2) if len(output2_match.groups()) > 1 and output2_match.group(
                    2) else "1"
                if output2_count_raw != '0':  # Only add if count > 0
                    output2_count_display = str(int(float(output2_count_raw)))
                    output2_node_id = f"{output2_name}_{output2_count_raw}"

                    if output2_node_id not in item_nodes:
                        item_nodes[output2_node_id] = output2_node_id
                        dot.node(output2_node_id, f"{output2_name}\n({output2_count_display})", shape='box')
                        dot.edge(action_id, item_nodes[output2_node_id])

            # Process output3 (updated count of input2)
            if output3_match:
                output3_name = output3_match.group(1)
                output3_count_raw = output3_match.group(2) if len(output3_match.groups()) > 1 and output3_match.group(
                    2) else "1"
                if output3_count_raw != '0':  # Only add if count > 0
                    output3_count_display = str(int(float(output3_count_raw)))
                    output3_node_id = f"{output3_name}_{output3_count_raw}"

                    if output3_node_id not in item_nodes:
                        item_nodes[output3_node_id] = output3_node_id
                        dot.node(output3_node_id, f"{output3_name}\n({output3_count_display})", shape='box')
                        dot.edge(action_id, item_nodes[output3_node_id])

    # Add final total nodes only for items that have a non-zero count in the final inventory
    for item_name in final_inventory:
        if item_name not in ["Step", "Action"]:  # Skip non-item columns
            final_count = final_inventory[item_name]

            # Only add final nodes for items with a value greater than 0 in the final inventory
            if final_count > 0:
                final_node_id = f"final_{item_name}"

                # Always display as integer
                final_count_display = str(int(final_count))

                if item_name in ['Currency', 'Shards', 'Perks', 'Dust', 'Skill']:
                    dot.node(final_node_id, f"FINAL {item_name}\n({final_count_display})",
                             shape='box', style='filled', fillcolor='orange', penwidth='2')
                elif item_name not in all_ingredients:
                    dot.node(final_node_id, f"FINAL {item_name}\n({final_count_display})",
                             shape='box', style='filled', fillcolor='yellow', penwidth='2')
                else:
                    dot.node(final_node_id, f"FINAL {item_name}\n({final_count_display})",
                             shape='box', style='filled', fillcolor='lightblue', penwidth='2')

                # Connect all nodes of this type to the final node
                for node_id in item_nodes:
                    if node_id.startswith(f"{item_name}_"):
                        node_count_match = re.match(fr"{item_name}_(.+)", node_id)
                        if node_count_match:
                            node_count_raw = node_count_match.group(1)
                            try:
                                node_count_float = float(node_count_raw)
                                if abs(node_count_float - final_count) < 0.01:
                                    dot.edge(node_id, final_node_id, style='dashed')
                            except ValueError:
                                if node_count_raw == str(final_count):
                                    dot.edge(node_id, final_node_id, style='dashed')

    return dot


def render_graph_visualization(combos_used, ingredient_counts, total_loot, formatted_combos=None):
    """
    Create and display a graph visualization of the alchemy combinations.

    Args:
        combos_used (list): List of tuples (combo, count, product)
        ingredient_counts (dict): Dictionary of ingredient counts
        total_loot (dict): Dictionary of total loot by type
        formatted_combos (list, optional): List of dicts with formatted combo data
    """
    try:
        # If formatted_combos is provided, use it directly
        if formatted_combos:
            # Track inventory using formatted combos
            inventory_df = track_inventory_from_formatted_combos(ingredient_counts, formatted_combos)

            # Create transition dataframe
            transition_df = create_transition_df_from_inventory(inventory_df)
        else:
            # Use the original approach with inventory_tracking module
            from inventory_tracking import prepare_visualization_data
            inventory_df, transition_df = prepare_visualization_data(combos_used, ingredient_counts)

        # Create the graphviz visualization
        dot = create_crafting_visualization(transition_df, inventory_df)

        # Display the results with a wider configuration
        st.caption("Note: This visualization shows the flow of ingredients through the optimization process. The loot is a running total, not just from that combination.")
        st.graphviz_chart(dot, use_container_width=True)  # Use full container width

        # Add explanation of the visualization
        st.info("""
        **Visualization Legend:**
        - **Squares**: Ingredients with their quantities
        - **Triangles**: Combination operations with their multiplier
        - **Yellow Squares**: Rewards/loot obtained
        - **Orange Squares**: Final totals for currency and rewards
        - **Light Blue Squares**: Final totals for ingredients

        Follow the arrows to see the flow of ingredients through the crafting process!
        """)

    except Exception as e:
        st.error(f"Error creating visualization: {str(e)}")
        st.exception(e)

    return inventory_df
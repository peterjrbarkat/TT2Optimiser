import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.config import get_ingredient_images
from src.graph_visualisation import render_graph_visualization
from src.inventory_tracking import track_inventory_from_formatted_combos
from src.inventory_tracking import highlight_changes
import os
import hashlib
from src.genai_client import extract_counts_from_image
from src.optimizer import (
    FRONTIER_GAPS_PER_ITERATION,
    FRONTIER_POINTS,
    FRONTIER_REFINEMENTS,
    MAX_PER_ITEM_FIRST_BATCH,
    MAX_PER_ITEM_LOOT,
    extract_loot,
    frontier_weight_sets,
    refinement_shares,
    refinement_should_stop,
    share_label,
    solve_plan,
    weights_for_share,
)
from src.render_combo import render_results
from src.run_logging import log_run, fetch_runs, is_logging_configured
from src.run_visualisation import render_runs_analysis

ingredient_images = get_ingredient_images()

# Load the CSV file
file_path = 'TT2 Alchemy Event.csv'
df = pd.read_csv(file_path, index_col=0)

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
loot_df = df.map(lambda x: extract_loot(x, default_importance_scores.keys()))

# Extracting relevant data for optimization
items = list(df.index)
combinations = [(i, j) for i in items for j in items if i <= j]

# Streamlit inputs
st.set_page_config(layout="wide")
st.title("TT2 Alchemy Event Optimizer")

st.success("Updated for September 2026 Event! For any feedback or bugs, please reach out to peterbarkat@gmail.com")
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
    edited_ingredient_data = st.data_editor(ingredient_data, num_rows="fixed", width="stretch", hide_index=True)
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

    edited_importance_data = st.data_editor(importance_data, num_rows="fixed", width="stretch", hide_index=True)
    for index, row in edited_importance_data.iterrows():
        importance_scores[row["Loot Type"]] = float(row["Importance"])

def format_weight(weight):
    if abs(weight - round(weight)) < 1e-6:
        return str(int(round(weight)))
    return f"{weight:.4g}"


def selected_point_index(event):
    """Index of the first clicked Plotly point, if the chart reported one."""
    if event is None:
        return None
    selection = event.get("selection") if isinstance(event, dict) else getattr(event, "selection", None)
    if selection is None:
        return None
    points = selection.get("points") if isinstance(selection, dict) else getattr(selection, "points", None)
    if not points:
        return None
    point = points[0]
    if not hasattr(point, "get"):
        point = {name: getattr(point, name, None) for name in ("point_index", "point_number", "customdata")}
    custom = point.get("customdata")
    if isinstance(custom, (int, float)) and not isinstance(custom, bool):
        return int(custom)
    if isinstance(custom, (list, tuple)) and custom and isinstance(custom[0], (int, float)):
        return int(custom[0])
    for key in ("point_index", "point_number"):
        if point.get(key) is not None:
            return int(point[key])
    return None


def render_scenario_bar(title, weights):
    st.markdown(f"**Chosen scenario:** {title}")
    chips = []
    for name, weight in weights.items():
        shown = format_weight(weight)
        if weight > 0:
            chips.append(
                "<span style='display:inline-block;margin:0 6px 6px 0;padding:4px 10px;"
                "border-radius:999px;border:2px solid #1f6feb;font-weight:700;'>"
                f"{name}: {shown}</span>"
            )
        else:
            chips.append(
                "<span style='display:inline-block;margin:0 6px 6px 0;padding:4px 10px;"
                "border-radius:999px;border:1px solid #bbbbbb;opacity:0.55;'>"
                f"{name}: 0</span>"
            )
    st.markdown("".join(chips), unsafe_allow_html=True)


def render_route(plan):
    render_results(plan["total_score"], plan["combos_used"], plan["total_loot"], ingredient_images)
    st.subheader("Check brews:")
    st.write("Changes in the quantities are highlighted in yellow")
    inventory = track_inventory_from_formatted_combos(plan["ingredient_counts"], plan["formatted_combos"])
    st.write(highlight_changes(inventory))
    with st.expander("Visualise results - (Experimental)", expanded=False):
        render_graph_visualization(
            plan["combos_used"], plan["ingredient_counts"], plan["total_loot"], plan["formatted_combos"]
        )


def solve_focused(loot_name, counts):
    weights = {key: 0.0 for key in default_importance_scores}
    weights[loot_name] = 100.0
    plan = solve_plan(df, items, combinations, counts, weights)
    plan["label"] = f"Max {loot_name}"
    plan["focus"] = loot_name
    return plan


def load_max_plans(loot_names, counts):
    plans = []
    total = len(loot_names)
    progress = st.progress(0, text="Loading...")
    for index, loot_name in enumerate(loot_names):
        progress.progress(index / total, text=f"Loading {index + 1} of {total}: {loot_name}")
        plans.append(solve_focused(loot_name, counts))
    progress.progress(1.0, text="Loading complete")
    progress.empty()
    return plans


def _frontier_point(item_a, item_b, share, weights, plan):
    plan = dict(plan)
    plan["weights"] = {key: float(weights[key]) for key in weights}
    plan["label"] = share_label(item_a, item_b, share)
    plan["total_score"] = sum(plan["weights"].get(name, 0) * amount for name, amount in plan["total_loot"].items())
    return {
        "share": share,
        "label": plan["label"],
        "plan": plan,
        "qty_a": plan["total_loot"].get(item_a, 0),
        "qty_b": plan["total_loot"].get(item_b, 0),
    }


def load_frontier(item_a, item_b, counts):
    """Evenly spaced trade-off, then extra solves in the steepest gaps."""
    progress = st.progress(0, text="Loading...")
    total_steps = FRONTIER_POINTS + FRONTIER_REFINEMENTS * FRONTIER_GAPS_PER_ITERATION
    progress.progress(0, text=f"Loading maximum {item_a}...")
    plan_a = solve_focused(item_a, counts)
    max_a = plan_a["total_loot"].get(item_a, 0)
    progress.progress(1 / total_steps, text=f"Loading maximum {item_b}...")
    plan_b = solve_focused(item_b, counts)
    max_b = plan_b["total_loot"].get(item_b, 0)
    loot_keys = list(default_importance_scores.keys())
    weight_sets = frontier_weight_sets(item_a, item_b, max_a, max_b, loot_keys)
    if weight_sets is None:
        missing = item_a if max_a <= 0 else item_b
        progress.empty()
        return {
            "item_a": item_a,
            "item_b": item_b,
            "error": f"{missing} cannot be crafted from the current ingredients.",
            "points": [],
        }

    points = []
    last = len(weight_sets) - 1
    for index, (share, weights) in enumerate(weight_sets):
        label = share_label(item_a, item_b, share)
        progress.progress(
            (index + 1) / total_steps,
            text=f"Loading trade-off {index + 1} of {FRONTIER_POINTS}: {label}",
        )
        if index == 0:
            plan = plan_a
        elif index == last:
            plan = plan_b
        else:
            plan = solve_plan(df, items, combinations, counts, weights)
        points.append(_frontier_point(item_a, item_b, share, weights, plan))

    completed = FRONTIER_POINTS
    seen_mixes = {(point["qty_a"], point["qty_b"]) for point in points}
    discovered_new_mix = False
    stale_rounds = 0
    for step in range(FRONTIER_REFINEMENTS):
        shares = refinement_shares(points, max_a, max_b)
        if not shares:
            break
        fresh = 0
        for gap_index, share in enumerate(shares):
            completed += 1
            label = share_label(item_a, item_b, share)
            progress.progress(
                min(completed / total_steps, 1),
                text=(
                    f"Loading refinement {step + 1} of up to {FRONTIER_REFINEMENTS}, "
                    f"sample {gap_index + 1} of {len(shares)}: {label}"
                ),
            )
            weights = weights_for_share(item_a, item_b, max_a, max_b, loot_keys, share)
            plan = solve_plan(df, items, combinations, counts, weights)
            point = _frontier_point(item_a, item_b, share, weights, plan)
            mix = (point["qty_a"], point["qty_b"])
            if mix not in seen_mixes:
                fresh += 1
                seen_mixes.add(mix)
            points.append(point)
        if fresh:
            discovered_new_mix = True
            stale_rounds = 0
        else:
            stale_rounds += 1
        if refinement_should_stop(discovered_new_mix, stale_rounds):
            break

    points.sort(key=lambda point: point["share"])
    progress.empty()
    return {"item_a": item_a, "item_b": item_b, "error": None, "points": points}


def apply_chart_selection(event, state_key, size):
    picked = selected_point_index(event)
    if picked is None or not 0 <= picked < size:
        return
    if picked != st.session_state.get(state_key):
        st.session_state[state_key] = picked
        st.rerun()


loot_names = list(default_importance_scores)
st.divider()
run_col, max_col, from_col, toward_col, trade_col = st.columns(
    [1.15, 1.3, 1.25, 1.25, 1.35], vertical_alignment="bottom"
)
with run_col:
    run_optimizer = st.button("Run optimizer", type="primary", width="stretch")
with max_col:
    run_max = st.button("Max of each item", width="stretch")
with from_col:
    trade_a = st.selectbox("Trade-off from", loot_names, index=0, key="trade_from")
with toward_col:
    trade_b = st.selectbox("Toward", loot_names, index=loot_names.index("Skill Points"), key="trade_toward")
with trade_col:
    run_trade = st.button("Explore trade-off", width="stretch")

if run_optimizer:
    with st.spinner("Loading..."):
        plan = solve_plan(df, items, combinations, ingredient_counts, importance_scores)
    plan["label"] = "Your importance scores"
    st.session_state["optimization_output"] = plan
    st.session_state["explore_mode"] = "optimizer"
    log_run(
        ingredient_counts=dict(ingredient_counts),
        importance_scores=dict(importance_scores),
        ingredient_order=items,
        loot_order=list(default_importance_scores.keys()),
    )

if run_max:
    with st.spinner("Loading..."):
        st.session_state["max_results"] = load_max_plans(MAX_PER_ITEM_LOOT[:MAX_PER_ITEM_FIRST_BATCH], ingredient_counts)
    st.session_state["max_selected"] = 0
    st.session_state["explore_mode"] = "max"

if run_trade:
    if trade_a == trade_b:
        st.warning("Pick two different loot types for the trade-off.")
    else:
        with st.spinner("Loading..."):
            st.session_state["frontier"] = load_frontier(trade_a, trade_b, ingredient_counts)
        st.session_state["frontier_selected"] = 0
        st.session_state["explore_mode"] = "frontier"

mode = st.session_state.get("explore_mode")
if mode == "optimizer" and "optimization_output" in st.session_state:
    chosen = st.session_state["optimization_output"]
    render_scenario_bar(chosen["label"], chosen["weights"])
    render_route(chosen)
elif mode == "max" and st.session_state.get("max_results"):
    max_results = st.session_state["max_results"]
    if len(max_results) < len(MAX_PER_ITEM_LOOT):
        remaining = MAX_PER_ITEM_LOOT[len(max_results):]
        st.caption(f"Showing the first {len(max_results)} of {len(MAX_PER_ITEM_LOOT)}. Still to run: {', '.join(remaining)}.")
        if st.button("Load the remaining items"):
            with st.spinner("Loading..."):
                st.session_state["max_results"] = max_results + load_max_plans(
                    remaining, max_results[0]["ingredient_counts"]
                )
            st.rerun()
    selected = min(st.session_state.get("max_selected", 0), len(max_results) - 1)
    chosen = max_results[selected]
    render_scenario_bar(chosen["label"], chosen["weights"])
    quantities = [plan["total_loot"].get(plan["focus"], 0) for plan in max_results]
    max_fig = go.Figure(
        go.Bar(
            x=[plan["focus"] for plan in max_results],
            y=quantities,
            marker_color=["#f5a524" if index == selected else "#4c78a8" for index in range(len(max_results))],
            text=[str(int(amount)) for amount in quantities],
            textposition="auto",
            customdata=list(range(len(max_results))),
            hovertemplate="%{x}: %{y:.0f}<extra></extra>",
        )
    )
    max_fig.update_layout(
        title="Most you can get of each item",
        height=420,
        margin=dict(l=10, r=10, t=50, b=10),
        yaxis_title="Quantity",
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    max_event = st.plotly_chart(max_fig, width="stretch", on_select="rerun", key="max_chart", selection_mode="points")
    apply_chart_selection(max_event, "max_selected", len(max_results))
    with st.expander("Brew route", expanded=True):
        render_route(max_results[min(st.session_state.get("max_selected", 0), len(max_results) - 1)])
elif mode == "frontier" and st.session_state.get("frontier"):
    frontier = st.session_state["frontier"]
    if frontier.get("error"):
        st.warning(frontier["error"])
    else:
        points = frontier["points"]
        selected = min(st.session_state.get("frontier_selected", 0), len(points) - 1)
        chosen = points[selected]["plan"]
        render_scenario_bar(chosen["label"], chosen["weights"])
        st.caption(
            "Starts with 5 evenly spaced points, then adds pairs where the totals change the most. Stops after two rounds that only repeat mixes already found."
        )
        frontier_fig = go.Figure(
            go.Scatter(
                x=[point["qty_a"] for point in points],
                y=[point["qty_b"] for point in points],
                mode="lines+markers+text",
                text=[point["label"] if index in (0, selected, len(points) - 1) else "" for index, point in enumerate(points)],
                textposition="top center",
                hovertext=[point["label"] for point in points],
                marker=dict(
                    size=[18 if index == selected else 10 for index in range(len(points))],
                    color=["#f5a524" if index == selected else "#4c78a8" for index in range(len(points))],
                ),
                customdata=list(range(len(points))),
                hovertemplate="%{hovertext}<br>" + frontier["item_a"] + ": %{x:.0f}<br>" + frontier["item_b"] + ": %{y:.0f}<extra></extra>",
            )
        )
        frontier_fig.update_layout(
            title=f"{frontier['item_a']} vs {frontier['item_b']}",
            height=480,
            margin=dict(l=10, r=10, t=50, b=10),
            xaxis_title=frontier["item_a"],
            yaxis_title=frontier["item_b"],
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        frontier_event = st.plotly_chart(
            frontier_fig, width="stretch", on_select="rerun", key="frontier_chart", selection_mode="points"
        )
        apply_chart_selection(frontier_event, "frontier_selected", len(points))
        with st.expander("Brew route", expanded=True):
            shown = points[min(st.session_state.get("frontier_selected", 0), len(points) - 1)]
            st.caption(
                f"{shown['label']}: {int(shown['qty_a'])} {frontier['item_a']}, {int(shown['qty_b'])} {frontier['item_b']}."
            )
            render_route(shown["plan"])
else:
    st.info("Set your ingredients and importance scores, then click **Run optimizer**, **Max of each item**, or **Explore trade-off**.")

# --- Community run statistics (aggregated across all logged runs) ---
st.divider()
with st.expander("Community run statistics", expanded=False):
    if not is_logging_configured():
        st.info("Run logging is not configured. Add the Google Sheets backend in secrets to enable this section.")
    else:
        runs_df = fetch_runs()
        render_runs_analysis(runs_df, ingredient_names=items, loot_names=list(default_importance_scores.keys()))

        # Admin-only raw export, gated by a secret token in the URL query param.
        admin_token = None
        try:
            admin_token = st.secrets.get("admin_token")
        except Exception:
            admin_token = None
        provided_token = st.query_params.get("admin")

        if admin_token and provided_token == admin_token:
            st.divider()
            st.subheader("Admin export")
            if runs_df is not None and not runs_df.empty:
                st.download_button(
                    "Download all runs (CSV)",
                    data=runs_df.to_csv(index=False).encode("utf-8"),
                    file_name="all_runs.csv",
                    mime="text/csv",
                )
            else:
                st.info("No runs to export yet.")

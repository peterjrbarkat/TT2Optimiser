"""Aggregate visualisations across all logged optimizer runs.

- Ingredients: a box per ingredient whose box spans the 40th-60th percentile
  of the input counts, with the median marked.
- Loot: a "vote" tally. For each run, the loot type with the highest importance
  score gets +1 vote; if several tie for the highest, each tied type gets +0.1.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

_TIMESTAMP_COL = "timestamp"


def _percentile_summary(runs_df: pd.DataFrame, ingredient_names) -> pd.DataFrame:
    """Return a tidy p40/median/p60 table for each ingredient present in the data."""
    rows = []
    for name in ingredient_names:
        if name not in runs_df.columns:
            continue
        series = pd.to_numeric(runs_df[name], errors="coerce").dropna()
        if series.empty:
            continue
        p40, p50, p60 = np.percentile(series, [40, 50, 60])
        rows.append(
            {
                "Ingredient": name,
                "p40": round(float(p40), 3),
                "median": round(float(p50), 3),
                "p60": round(float(p60), 3),
                "n_runs": int(series.size),
            }
        )
    return pd.DataFrame(rows)


def _loot_votes(runs_df: pd.DataFrame, loot_names) -> pd.DataFrame:
    """Tally loot votes: +1 for a clear per-run max, +0.1 each when tied."""
    present = [name for name in loot_names if name in runs_df.columns]
    votes = {name: 0.0 for name in present}
    if not present:
        return pd.DataFrame(columns=["Loot Type", "Votes"])

    numeric = runs_df[present].apply(pd.to_numeric, errors="coerce")
    for _, row in numeric.iterrows():
        vals = row.dropna()
        if vals.empty:
            continue
        max_val = vals.max()
        winners = vals[vals == max_val].index.tolist()
        if len(winners) == 1:
            votes[winners[0]] += 1.0
        else:
            for winner in winners:
                votes[winner] += 0.1

    result = pd.DataFrame({"Loot Type": list(votes.keys()), "Votes": list(votes.values())})
    total = result["Votes"].sum()
    result["Votes %"] = (result["Votes"] / total * 100).round(2) if total > 0 else 0.0
    result["Votes"] = result["Votes"].round(2)
    return result.sort_values("Votes %", ascending=False).reset_index(drop=True)


def render_runs_analysis(runs_df: pd.DataFrame, ingredient_names, loot_names) -> None:
    """Render the community-run analytics section."""
    if runs_df is None or runs_df.empty:
        st.info("No runs have been logged yet. Run the optimizer to start building the dataset.")
        return

    # --- Total ingredients per run ---
    present = [name for name in ingredient_names if name in runs_df.columns]
    totals = runs_df[present].apply(pd.to_numeric, errors="coerce").sum(axis=1).dropna()
    if not totals.empty:
        t40, t50, t60 = np.percentile(totals, [40, 50, 60])
        st.markdown("#### Total ingredients per run")
        m40, m50, m60 = st.columns(3)
        m40.metric("40th percentile", f"{t40:.0f}")
        m50.metric("Median", f"{t50:.0f}")
        m60.metric("60th percentile", f"{t60:.0f}")

    # --- Ingredient box plots (40th-60th percentile, with median) ---
    st.markdown("**Ingredient counts (40th-60th percentile, median marked)**")
    summary = _percentile_summary(runs_df, ingredient_names)
    if summary.empty:
        st.info("No numeric ingredient data available yet.")
    else:
        ingredients = summary["Ingredient"].tolist()
        customdata = summary[["p40", "median", "p60", "n_runs"]].to_numpy()
        fig = go.Figure()
        # Coloured bar spanning the 40th-60th percentile for each ingredient.
        fig.add_trace(
            go.Bar(
                x=ingredients,
                base=summary["p40"],
                y=(summary["p60"] - summary["p40"]),
                width=0.6,
                marker_color="#7c5cff",
                name="40th-60th percentile",
                customdata=customdata,
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "p60: %{customdata[2]}<br>"
                    "median: %{customdata[1]}<br>"
                    "p40: %{customdata[0]}<br>"
                    "runs: %{customdata[3]}<extra></extra>"
                ),
            )
        )
        # X marker at the median.
        fig.add_trace(
            go.Scatter(
                x=ingredients,
                y=summary["median"],
                mode="markers",
                marker=dict(symbol="x", size=11, color="#111111", line=dict(width=1)),
                name="median",
                hovertemplate="<b>%{x}</b><br>median: %{y}<extra></extra>",
            )
        )
        fig.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis_title="Input count (log scale)",
            xaxis_title="Ingredient",
            margin=dict(l=10, r=10, t=10, b=10),
            height=420,
        )
        # One labelled column per ingredient.
        fig.update_xaxes(
            type="category",
            categoryorder="array",
            categoryarray=ingredients,
            tickangle=-45,
        )
        # Log y-axis (non-positive percentile values are simply not plotted).
        fig.update_yaxes(type="log")
        # The Plotly modebar provides a built-in PNG download for the chart.
        st.plotly_chart(fig, use_container_width=True)

        st.download_button(
            "Download chart data (CSV)",
            data=summary.to_csv(index=False).encode("utf-8"),
            file_name="ingredient_percentiles.csv",
            mime="text/csv",
        )

    st.divider()

    # --- Loot vote tally ---
    st.markdown("**Loot importance votes** (per run: top loot +1, ties +0.1 each)")
    st.caption("Note: the default importance puts Currency highest, so expect Currency to dominate the votes.")
    votes = _loot_votes(runs_df, loot_names)
    if votes.empty or votes["Votes"].sum() == 0:
        st.info("No loot importance data available yet.")
    else:
        vote_fig = go.Figure(
            go.Bar(
                x=votes["Loot Type"],
                y=votes["Votes %"],
                marker_color="#7c5cff",
                hovertemplate="<b>%{x}</b><br>%{y}% of votes<extra></extra>",
            )
        )
        vote_fig.update_layout(
            yaxis_title="Share of votes (%)",
            xaxis_title="Loot type",
            margin=dict(l=10, r=10, t=10, b=10),
            height=420,
        )
        st.plotly_chart(vote_fig, use_container_width=True)
        st.download_button(
            "Download vote data (CSV)",
            data=votes.to_csv(index=False).encode("utf-8"),
            file_name="loot_votes.csv",
            mime="text/csv",
        )

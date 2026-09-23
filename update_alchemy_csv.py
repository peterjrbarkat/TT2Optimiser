"""Clean a TT2 Alchemy recipe matrix and update TT2 Alchemy Event.csv when every cell validates.

Usage:
    python update_alchemy_csv.py --source "<Google Sheets URL | file.xlsx | file.csv>" [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.alchemy_cleaner import CleanerError, CleanResult, run_clean

ROOT = Path(__file__).resolve().parent


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", required=True, help="Google Sheets URL (with gid), .xlsx, or .csv")
    parser.add_argument("--dry-run", action="store_true", help="validate and report without replacing the CSV")
    parser.add_argument("--target", default=str(ROOT / "TT2 Alchemy Event.csv"), help="production CSV")
    parser.add_argument("--sheet", help="worksheet name, local .xlsx only")
    args = parser.parse_args(argv)

    source = args.source
    if not source.startswith(("http://", "https://")) and not Path(source).is_file() and (ROOT / source).is_file():
        source = str(ROOT / source)
    target = Path(args.target).resolve()
    try:
        result = run_clean(
            source,
            target=target,
            report_dir=ROOT / ".alchemy",
            streamlit_path=ROOT / "streamlit_app.py",
            dry_run=args.dry_run,
            sheet=args.sheet,
        )
    except CleanerError as exc:
        print(f"FAIL — {target.name} NOT UPDATED\n\n{exc}\n\nProduction CSV was left unchanged.")
        return 1
    print(render_summary(result))
    return 0 if result.passed else 1


def render_summary(result: CleanResult) -> str:
    c = result.counts
    name = result.target.name
    lines = [
        "PASS — candidate is compatible with TT2Optimiser" if result.passed else f"FAIL — {name} NOT UPDATED",
        "",
        "Source:",
        result.source,
        "",
        "Detected matrix:",
        result.matrix,
        f"{len(result.ingredients)} ingredients",
        f"{result.cell_count} recipe cells",
        "",
        "Validation:",
        f"{result.valid_cells} / {result.cell_count} valid",
        f"{c['blank']} blank",
        f"{c['unsupported']} unsupported",
        f"{c['ambiguous']} ambiguous",
        f"{c['compound_reward']} compound rewards",
        f"{len(result.conflicts)} symmetry conflicts",
        f"{len(result.mirrored)} blank cells mirrored from their symmetric pair",
        "",
        f"MAPPING COVERAGE: {result.mapping_coverage:.3g}%",
        "",
        "Cell types:",
        f"{c['ingredient']} ingredient results",
        f"{c['supported_reward']} supported reward results",
        "",
        "Normalisations:",
        *([f"{rule}: {n}" for rule, n in result.normalisations.most_common()] or ["(none)"]),
    ]

    d = result.diff
    lines += ["", "Comparison with existing production CSV:"]
    if d["had_existing"]:
        lines += [
            f"old ingredient count: {d['old_ingredient_count']}",
            f"new ingredient count: {d['new_ingredient_count']}",
            f"ingredients added: {_join(d['ingredients_added'])}",
            f"ingredients removed: {_join(d['ingredients_removed'])}",
            f"recipe cells unchanged: {d['cells_unchanged']}",
            f"recipe cells changed: {d['cells_changed']}",
            f"old reward types: {_join(d['old_reward_types'])}",
            f"new reward types: {_join(d['new_reward_types'])}",
            f"reward types added: {_join(d['reward_types_added'])}",
            f"reward types removed: {_join(d['reward_types_removed'])}",
        ]
    else:
        lines.append("no existing production CSV")

    if result.passed:
        lines += [
            "",
            f"All {result.cell_count} recipe cells resolve to either:",
            "- an exact current ingredient, or",
            "- an exact reward key currently supported by streamlit_app.py.",
            "",
            f"{name} updated." if result.updated else f"Dry run: {name} was not modified.",
        ]
        return "\n".join(lines)

    lines += ["", f"{result.cell_count - result.valid_cells} cells require attention:"]
    for issue in result.issues():
        where = f" ({issue['cell']})" if issue["cell"] else ""
        lines.append(f"{issue['row_ingredient']} + {issue['column_ingredient']}{where}:")
        lines.append(f"  source = {issue['source_value']!r}")
        if issue["classification"] == "unsupported":
            lines.append(f"  parsed reward = {issue['parsed_reward']!r}")
            lines.append("  current optimiser supports this = NO")
        else:
            lines.append(f"  classification = {issue['classification']}")
    for row, col, left, right in result.conflicts:
        lines.append(f"{row} + {col}: symmetry conflict {left!r} vs {right!r}")
    lines += [*result.problems, "", "Production CSV was left unchanged."]
    return "\n".join(lines)


def _join(values: list[str]) -> str:
    return ", ".join(values) if values else "(none)"


if __name__ == "__main__":
    sys.exit(main())

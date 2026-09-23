---
name: tt2-alchemy-cleaner
description: Download and clean a Tap Titans 2 Alchemy recipe matrix, validate every cell against the current TT2Optimiser reward schema, and safely update TT2 Alchemy Event.csv.
disable-model-invocation: true
---

# TT2 Alchemy Cleaner

When invoked, expect the user to provide a Google Sheets URL or a local CSV/XLSX.

1. Run:

   python update_alchemy_csv.py --source "<provided source>"

2. Do not manually clean spreadsheet values yourself.

3. The deterministic Python cleaner is the source of truth.

4. Read the cleaner's output and `.alchemy/validation_report.json`.

5. If PASS:
   - state that mapping coverage is 100%;
   - state the number of validated cells;
   - summarise automatic mappings;
   - summarise differences versus the previous production CSV;
   - confirm that `TT2 Alchemy Event.csv` was replaced;
   - note that the screenshot prompt in `src/genai_client.py` builds its ingredient order from the CSV, so it follows the new sheet order with no edits.

6. If FAIL:
   - do not manually edit the production CSV to make it pass;
   - do not invent a semantic mapping;
   - report every distinct unsupported/ambiguous value;
   - include the ingredient pair(s) where it occurs;
   - state clearly that the production CSV was not modified.

7. If the user asks to add support for a new reward:
   - first determine whether that reward should be added to the actual optimiser;
   - do not make the cleaner claim the optimiser supports something it does not.

import os
import json
import re
from typing import Dict, List, Optional, Tuple


def _get_api_key(preferred_api_key: Optional[str] = None) -> Optional[str]:
    # Priority: explicit param > st.secrets > env var
    if preferred_api_key:
        return preferred_api_key
    try:
        import streamlit as st  # local import to avoid hard dependency if not used
        if hasattr(st, "secrets") and "GOOGLE_CLOUD_API_KEY" in st.secrets:
            return st.secrets["GOOGLE_CLOUD_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GOOGLE_CLOUD_API_KEY")


def _parse_counts_from_json_like(
    obj_or_text, ingredient_names: List[str]
) -> Dict[str, int]:
    # Initialize all to 0
    counts: Dict[str, int] = {name: 0 for name in ingredient_names}

    # 1) If it's already a dict of numbers, coerce
    if isinstance(obj_or_text, dict):
        # Some APIs return {"response": "..."}; handle that below
        if all(
            k in ingredient_names and isinstance(v, (int, float, str))
            for k, v in obj_or_text.items()
        ):
            for k, v in obj_or_text.items():
                try:
                    counts[k] = int(v)
                except Exception:
                    counts[k] = 0
            return counts

        # Fallback if dict has "response" string
        if "response" in obj_or_text and isinstance(obj_or_text["response"], str):
            obj_or_text = obj_or_text["response"]
        else:
            # Unknown dict shape; return zeros
            return counts

    # 2) If it's a string like "Leaf: 12, Sand: 15, ..."
    if isinstance(obj_or_text, str):
        # Extract pairs "Name: number"
        # Match ingredient names with letters/spaces and integer counts
        pairs = re.findall(r"([A-Za-z ]+)\s*:\s*(-?\d+)", obj_or_text)
        for name, num_str in pairs:
            normalized = name.strip()
            if normalized in counts:
                try:
                    counts[normalized] = int(num_str)
                except Exception:
                    counts[normalized] = 0
        return counts

    # 3) Unknown type; return zeros
    return counts


def extract_counts_from_image(
    image_bytes: bytes,
    mime_type: Optional[str],
    ingredient_names: List[str],
    api_key: Optional[str] = None,
) -> Tuple[str, Dict[str, int]]:
    """
    Calls Google GenAI to extract ingredient counts from the provided image.
    Returns (raw_text_response, counts_dict).
    Secrets priority: provided api_key > st.secrets > env var
    """
    key = _get_api_key(api_key)
    if not key:
        return "Missing API key.", {name: 0 for name in ingredient_names}

    try:
        from google import genai
        from google.genai import types
    except Exception as e:
        return f"Failed to import google-genai. Please install 'google-genai'. Error: {e}", {
            name: 0 for name in ingredient_names
        }

    os.environ["GOOGLE_CLOUD_API_KEY"] = key

    client = genai.Client(
        vertexai=True,
        api_key=os.environ.get("GOOGLE_CLOUD_API_KEY"),
    )

    msg_image = types.Part.from_bytes(
        data=image_bytes,
        mime_type=mime_type or "image/jpeg",
    )

    # ingredient_names follows TT2 Alchemy Event.csv, i.e. the recipe sheet's header order.
    ingredient_list = ", ".join(ingredient_names)
    example = json.dumps({name: 2 for name in ingredient_names})
    prompt_text = f"""You are given a screenshot of TT2 alchemy ingredients.
Reading left to right, top to bottom, the ingredients appear in this exact order:
{ingredient_list}

Return a JSON object with EXACTLY these keys and integer values only:
{ingredient_list}

Example format (keys only, no extra text):
{example}

If an ingredient is missing, set it to 0.
Output must be JSON only."""

    msg_text = types.Part.from_text(text=prompt_text)

    # Ask the model to produce an object with integer properties per ingredient
    schema_properties = {name: {"type": "INTEGER"} for name in ingredient_names}
    generate_content_config = types.GenerateContentConfig(
        max_output_tokens=2048,
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ],
        response_mime_type="application/json",
        response_schema={
            "type": "OBJECT",
            "properties": schema_properties,
            "additionalProperties": False,
        },
        # gemini-3.8-flash rejects thinking_budget and the "minimal" level.
        thinking_config=types.ThinkingConfig(thinking_level="low"),
    )

    contents = [
        types.Content(
            role="user",
            parts=[msg_image, msg_text],
        ),
    ]

    # Stream and collect
    full_text = ""
    for chunk in client.models.generate_content_stream(
        model="gemini-3.8-flash",
        contents=contents,
        config=generate_content_config,
    ):
        if getattr(chunk, "text", None):
            full_text += chunk.text

    # Try to parse JSON directly; if not, fallback to flexible parsing
    parsed: Optional[dict] = None
    try:
        parsed = json.loads(full_text)
    except Exception:
        # Fallback: extract a JSON block if model wrapped it
        match = re.search(r"\{[\s\S]*\}", full_text)
        if match:
            try:
                parsed = json.loads(match.group(0))
            except Exception:
                parsed = None

    counts = _parse_counts_from_json_like(parsed if parsed is not None else full_text, ingredient_names)
    return full_text, counts



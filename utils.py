import streamlit as st


def set_custom_styles():
    """Set custom CSS styles for the application"""
    st.markdown("""
    <style>
        .ingredient-img {
            vertical-align: middle;
            margin-right: 5px;
        }
        .result-card {
            background-color: #f9f9f9;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .formula {
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
        }
        .plus-sign {
            margin: 0 10px;
            font-size: 24px;
            font-weight: bold;
        }
        .equals-sign {
            margin: 0 15px;
            font-size: 24px;
            font-weight: bold;
        }
        .count-badge {
            background-color: #007bff;
            color: white;
            border-radius: 15px;
            padding: 2px 8px;
            margin-right: 8px;
            font-weight: bold;
        }
        .currency {
            color: #f1c40f;
            font-weight: bold;
        }
        .header-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .total-container {
            background-color: #e3f2fd;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
        }
    </style>
    """, unsafe_allow_html=True)


def get_img_html(ingredient, ingredient_images, size=40):
    """Generate HTML for displaying an ingredient image with text

    Args:
        ingredient (str): The ingredient name
        ingredient_images (dict): Dictionary mapping ingredient names to image URLs
        size (int): Size of the image in pixels

    Returns:
        str: HTML string with the image and text
    """
    if ingredient in ingredient_images:
        return f'<img src="{ingredient_images[ingredient]}" width="{size}" height="{size}" style="vertical-align:middle"/> {ingredient}'
    return ingredient


def extract_loot(value, importance_keys):
    """Extract loot information from a string

    Args:
        value (str): The loot string in format "123 LootType"
        importance_keys (list): List of keys to check against

    Returns:
        tuple: (loot_type, amount)
    """
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
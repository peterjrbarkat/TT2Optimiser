import pandas as pd

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
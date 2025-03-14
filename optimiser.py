from pulp import LpMaximize, LpProblem, LpVariable, lpSum, value
from utils import extract_loot


def create_and_solve_lp_problem(df, combinations, ingredient_counts, importance_scores):
    """Create and solve the linear programming problem

    Args:
        df (pandas.DataFrame): The alchemy combinations dataframe
        combinations (list): List of tuples of ingredient combinations
        ingredient_counts (dict): Dictionary of ingredient counts
        importance_scores (dict): Dictionary of importance scores

    Returns:
        tuple: (total_score, combos_used, total_loot)
    """
    # Create a new LP problem
    prob = LpProblem("Maximize Loot Score", LpMaximize)

    # Define variables
    combo_vars = LpVariable.dicts("Combo", combinations, lowBound=0, cat='Integer')

    # Objective function: sum of (importance score * loot amount * variable) for each combination
    prob += lpSum([
        importance_scores.get(extract_loot(df.loc[combo], importance_scores.keys())[0], 0) *
        extract_loot(df.loc[combo], importance_scores.keys())[1] *
        combo_vars[combo]
        for combo in combinations
    ])

    # Constraints for each item
    for item in ingredient_counts.keys():
        # Used items constraints
        used = lpSum([combo_vars[combo] for combo in combinations if combo[0] == item]) + \
               lpSum([combo_vars[combo] for combo in combinations if combo[1] == item and combo[0] != item])

        # Created items constraints - ingredients created by other combinations
        created = lpSum([combo_vars[combo] for combo in combinations if df.loc[combo] == item])

        # The constraint: used ingredients <= initial count + created from other combinations
        prob += used <= ingredient_counts[item] + created

    # Solve the problem
    prob.solve()

    # Extract results
    combos_used = [(combo, value(var), df.loc[combo]) for combo, var in combo_vars.items() if value(var) > 0]

    # Calculate total loot and score
    total_loot = {}
    total_score = 0

    for combo, count, product in combos_used:
        product_name, product_amount = extract_loot(product, importance_scores.keys())
        if product_name in total_loot:
            total_loot[product_name] += product_amount * count
        else:
            total_loot[product_name] = product_amount * count
        total_score += importance_scores.get(product_name, 0) * product_amount * count

    formatted_combos = []
    for combo, count, product in combos_used:
        formatted_combos.append({
            'input1': combo[0],
            'input2': combo[1],
            'count': count,
            'result': product,
            'is_ingredient': not any(key in product for key in importance_scores.keys() if isinstance(product, str))
        })

    return total_score, combos_used, total_loot, formatted_combos
# helpers.py
def map_operator_to_sql(operator):
    """
    Convierte operadores del formulario a operadores SQL.
    """
    operator_map = {
        '==': '=',
        '!=': '!=',
        '>': '>',
        '>=': '>=',
        '<': '<',
        '<=': '<=',
        'contains': 'LIKE',
        'not_contains': 'NOT LIKE',
        'starts_with': 'LIKE',
        'ends_with': 'LIKE'
    }
    return operator_map.get(operator, '=')
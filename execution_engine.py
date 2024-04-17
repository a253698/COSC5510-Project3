# EXECUTION_ENGINE

from dml import DMLManager
from ddl import DDLManager
from storage import StorageManager
import logging
import re


# Configure logging to display debug information
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def execute_query(command):
    print(f"Debug execution engine execute query: {command}")
    storage_manager = StorageManager()
    dml_manager = DMLManager(storage_manager)
    ddl_manager = DDLManager()
    

    try:
        if 'type' in command:
            if command['type'] == 'select':
                conditions = command.get('where_clause', "")
                if 'join' in command and command['join'] is not None:
                    return handle_join(command, dml_manager, storage_manager)
                # elif any(func in command['columns'][0] for func in ['MAX', 'MIN', 'SUM']):
                #     return handle_aggregations(command, dml_manager, conditions)
                elif any(func in command['columns'][0] for func in ['MAX', 'MIN', 'SUM', 'AVG', 'COUNT']):
                    return handle_aggregations(command, dml_manager, conditions)

                else:
                    return dml_manager.select(command['main_table'], command['columns'], conditions)
            elif command['type'] == 'insert':
                return dml_manager.insert(command['table'], command['data'])
            elif command['type'] == 'delete':
                return dml_manager.delete(command['table'], command['conditions'])
            elif command['type'] == 'create':
                return ddl_manager.create_table(command['table_name'], command['columns'])
            elif command['type'] == 'drop':
                return ddl_manager.drop_table(command['table_name'])
        else:
            logging.error("Unsupported or missing SQL command type")
            return "Unsupported or missing SQL command type"
    except Exception as e:
        logging.error(f"Execution error: {e}")
        return f"Execution error: {e}"
    
def apply_where_clause(data, where_clause):
    import operator
    ops = {
        '=': operator.eq,
        '!=': operator.ne,
        '>': operator.gt,
        '<': operator.lt,
        '>=': operator.ge,
        '<=': operator.le
    }

    def evaluate(item):
        # Simple parser for conditions; assumes well-formed input
        conditions = where_clause.split(' AND ')
        for condition in conditions:
            left, op, right = [x.strip() for x in re.split(r"(=|!=|>|<|>=|<=)", condition)]
            if op in ['=', '!=', '>', '<', '>=', '<=']:
                # Handle quoted string comparison for direct values
                if right.startswith("'") or right.startswith('"'):
                    right = right[1:-1]  # Remove quotes
                elif right.isdigit():
                    right = int(right)
                if not ops[op](item[left], right):
                    return False
        return True

    return [row for row in data if evaluate(row)]

def parse_condition(condition):
    import re
    pattern = r'(\w+\.\w+)\s*(<=|>=|<>|!=|<|>|=)\s*(\w+\.\w+)'
    match = re.search(pattern, condition)
    return match.group(1), match.group(2), match.group(3)

def evaluate_condition(left_value, right_value, operator):
    # logging.debug(f"Evaluating condition: {left_value} {operator} {right_value}")
    if operator == '=':
        return left_value == right_value
    elif operator == '<':
        return left_value < right_value
    elif operator == '>':
        return left_value > right_value
    elif operator == '!=' or operator == '<>':
        return left_value != right_value
    elif operator == '<=':
        return left_value <= right_value
    elif operator == '>=':
        return left_value >= right_value
    else:
        raise ValueError("Unsupported operator")

def handle_join(command, dml_manager, storage_manager):
    # logging.debug("Starting handle_join function")
    main_table, main_alias = command['main_table'].split(' AS ')
    join_clause = command['join']
    join_table, join_alias = join_clause.replace('JOIN ', '').split(' ON ')[0].split(' AS ')
    
    # logging.debug(f"Main table: {main_table}, Alias: {main_alias}")
    # logging.debug(f"Join table: {join_table}, Alias: {join_alias}")

    columns_to_return = {col.split('.')[1]: col.split('.')[0] for col in command['columns']}
    # logging.debug(f"Columns to return: {columns_to_return}")

    main_data = storage_manager.get_table_data(main_table.strip())
    join_data = storage_manager.get_table_data(join_table.strip())

    # logging.debug(f"Main table data: {main_data}")
    # logging.debug(f"Join table data: {join_data}")

    joined_data = []
    join_condition = join_clause.split(' ON ')[1]
    left_field_with_alias, operator, right_field_with_alias = parse_condition(join_condition)

    # logging.debug(f"Join condition parsed: {left_field_with_alias} {operator} {right_field_with_alias}")

    left_field_alias, left_field = left_field_with_alias.split('.')
    right_field_alias, right_field = right_field_with_alias.split('.')

    for main_item in main_data:
        for join_item in join_data:
            # logging.debug(f"Comparing main item {main_item} with join item {join_item}")
            if evaluate_condition(main_item[left_field], join_item[right_field], operator):
                merged_item = {}
                for col, alias in columns_to_return.items():
                    if alias == main_alias.strip():
                        merged_item[f"{alias}.{col}"] = main_item[col]
                    if alias == join_alias.strip():
                        merged_item[f"{alias}.{col}"] = join_item[col]
                if merged_item not in joined_data:
                    joined_data.append(merged_item)
                    logging.debug(f"Joined item: {merged_item}")


    # logging.debug(f"Final joined data: {joined_data}")
    return joined_data

def evaluate_join_condition(row1, row2, condition):
    left, right = condition.split('=')
    column1 = left.split('.')[-1].strip()
    column2 = right.split('.')[-1].strip()
    return row1.get(column1) == row2.get(column2)

def extract_table_and_alias(table_expression):
    parts = table_expression.split(' AS ')
    if len(parts) > 1:
        # Ensure we remove any possible extra spaces that could affect matching
        return parts[0].strip(), parts[1].strip()
    return parts[0].strip(), None  # No alias, ensure no trailing spaces

# def handle_aggregations(command, dml_manager, conditions):
#     column = command['columns'][0].split('(')[1].split(')')[0]
#     func = command['columns'][0].split('(')[0].strip().upper()
    
#     aggregator = getattr(dml_manager, func.lower(), None)
#     if callable(aggregator):
#         return aggregator(command['main_table'], column, conditions)
#     else:
#         logging.error(f"DMLManager does not support {func} aggregation.")
#         return f"DMLManager does not support {func} aggregation."

def handle_aggregations(command, dml_manager, conditions):
    column = command['columns'][0].split('(')[1].split(')')[0]
    func = command['columns'][0].split('(')[0].strip().upper()
    
    aggregator = getattr(dml_manager, func.lower(), None)
    if callable(aggregator):
        print(f"Debug: Aggregation function: {func}({column})")
        print(f"Debug: Conditions: {conditions}")
        result = aggregator(command['main_table'], column, conditions)
        print(f"Debug: Aggregation result: {result}")
        return result
    else:
        logging.error(f"DMLManager does not support {func} aggregation.")
        return f"DMLManager does not support {func} aggregation."

def handle_select(command, dml_manager):
    if any(func in command['columns'][0] for func in ['MAX', 'MIN', 'SUM']):
        return handle_aggregations(command, dml_manager)
    else:
        return dml_manager.select(command['main_table'], command['columns'], command['conditions'])

def aggregate_max(command, dml_manager):
    data = dml_manager.select(command['main_table'], [command['column']], command.get('conditions'))
    return max(row[command['column']] for row in data)

def aggregate_min(command, dml_manager):
    data = dml_manager.select(command['main_table'], [command['column']], command.get('conditions'))
    return min(row[command['column']] for row in data)

def aggregate_sum(command, dml_manager):
    data = dml_manager.select(command['main_table'], [command['column']], command.get('conditions'))
    total = 0
    for row in data:
        try:
            # Convert to int before summing; use float if decimals are possible.
            total += int(row[command['column']])
        except ValueError:
            # Log or handle the case where conversion is not possible
            print(f"Warning: Non-numeric data encountered in {command['column']} and will be ignored: {row[command['column']]}")
    return total

def aggregate_avg(command, dml_manager):
    data = dml_manager.select(command['main_table'], [command['column']], command.get('conditions'))
    total = sum(item[command['column']] for item in data if item[command['column']] is not None)
    count = sum(1 for item in data if item[command['column']] is not None)
    return total / count if count != 0 else 0

def aggregate_count(command, dml_manager):
    data = dml_manager.select(command['main_table'], ['*'], command.get('conditions'))
    return len(data)

def apply_having_clause(data, having_clause):
    # Example: 'SUM(revenue) > 10000'
    field, condition = having_clause.split('>')
    field, agg_func = field.split('(')[1].split(')')
    value = int(condition.strip())
    agg_data = {
        'SUM': sum,
        'AVG': lambda x: sum(x) / len(x) if len(x) > 0 else 0
    }
    if agg_func in agg_data:
        result = agg_data[agg_func]([item[field.strip()] for item in data])
        return result > value
    return False

def order_data(data, order_clause):
    import operator
    field, order = order_clause.split()
    reverse = True if order.upper() == 'DESC' else False
    return sorted(data, key=lambda x: x[field], reverse=reverse)


def simulate_database_fetch(command):
    # This is a placeholder function that should be replaced with actual database interaction
    # Returning a mock result
    return "Mock result: Data fetched successfully"

def evaluate(condition, row1, row2):
    # Basic evaluation of a join condition, e.g., 'table1.id = table2.ref_id'
    
    column1, column2 = condition.split('=')
    column1 = column1.strip()
    column2 = column2.strip()
    return row1[column1] == row2[column2]

if __name__ == "__main__":
    def test_aggregations():
        storage_manager = StorageManager()
        dml_manager = DMLManager(storage_manager)
        
        commands = [
            {'type': 'select', 'main_table': 'employees', 'columns': ['AVG(age)'], 'conditions': None},
            {'type': 'select', 'main_table': 'employees', 'columns': ['COUNT(id)'], 'conditions': None}
        ]
        for command in commands:
            print(f"Result of {command['columns'][0]}: {handle_aggregations(command, dml_manager, command['conditions'])}")

    def test_order_by():
        data = [{'name': 'Alice', 'age': 32}, {'name': 'Bob', 'age': 24}, {'name': 'Charlie', 'age': 29}]
        ordered_data = order_data(data, 'age DESC')
        print("Data ordered by age DESC:")
        for item in ordered_data:
            print(item)

    # Running all tests
    # test_theta_join()
    test_aggregations()
    test_order_by()

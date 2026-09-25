import ast

# Read the source
src = open("/mnt/d/Project2/kensho/scripts/gen_status_data.py").read()
tree = ast.parse(src)

# Find the function
fn_node = None
for n in tree.body:
    if isinstance(n, ast.FunctionDef) and n.name == "_filter_proxy_check_rows":
        fn_node = n
        break

print("Found function:", fn_node is not None)

# Print the source of the function to see line numbers
print("\nFunction source:")
print(ast.get_source_segment(src, fn_node))

# Find the If statement we want to modify
for i, stmt in enumerate(fn_node.body):
    if isinstance(stmt, ast.If):
        print(f"\nFound If statement at index {i}")
        print("If test:", ast.dump(stmt.test))
        print("If test source:", ast.get_source_segment(src, stmt.test))
        # Print the full if statement
        if_stmt_source = ast.get_source_segment(src, stmt)
        print("Full if statement:")
        print(if_stmt_source)
        break
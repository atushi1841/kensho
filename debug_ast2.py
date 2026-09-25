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
print("Number of statements in function:", len(fn_node.body))

# Print each statement with its index
for i, stmt in enumerate(fn_node.body):
    print(f"\nStatement {i}: {ast.dump(stmt)[:100]}...")
    if isinstance(stmt, ast.If):
        print(f"  If test: {ast.dump(stmt.test)}")
        if hasattr(stmt.test, 'left'):
            print(f"  If test left: {ast.dump(stmt.test.left)}")
        if hasattr(stmt.test, 'ops'):
            print(f"  If test ops: {ast.dump(stmt.test.ops)}")
        if hasattr(stmt.test, 'comparators'):
            print(f"  If test comparators: {ast.dump(stmt.test.comparators)}")

# Now let's find the specific if statement we want:
# We're looking for: if prev_ts is None or prev_ts < gen_start:
for i, stmt in enumerate(fn_node.body):
    if isinstance(stmt, ast.If):
        # Check if it's the right if statement by looking at its structure
        test = stmt.test
        if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or):
            print(f"\nFound BoolOp Or at statement {i}")
            print(f"  Op: {ast.dump(test.op)}")
            print(f"  Number of values: {len(test.values)}")
            for j, val in enumerate(test.values):
                print(f"    Value {j}: {ast.dump(val)}")
                # Check if it's "prev_ts is None"
                if isinstance(val, ast.Compare):
                    print(f"      Is Compare: left={ast.dump(val.left) if hasattr(val, 'left') else 'N/A'}")
                    print(f"      Is Compare: ops={ast.dump(val.ops) if hasattr(val, 'ops') else 'N/A'}")
                    print(f"      Is Compare: comparators={ast.dump(val.comparators) if hasattr(val, 'comparators') else 'N/A'}")
                # Check if it's "prev_ts < gen_start"
                elif isinstance(val, ast.Compare):
                    print(f"      Is Compare: left={ast.dump(val.left) if hasattr(val, 'left') else 'N/A'}")
                    print(f"      Is Compare: ops={ast.dump(val.ops) if hasattr(val, 'ops') else 'N/A'}")
                    print(f"      Is Compare: comparators={ast.dump(val.comparators) if hasattr(val, 'comparators') else 'N/A'}")
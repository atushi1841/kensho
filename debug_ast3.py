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

# Find the While loop (statement 8)
while_loop = None
for stmt in fn_node.body:
    if isinstance(stmt, ast.While):
        while_loop = stmt
        break

if while_loop:
    print(f"\nFound While loop with {len(while_loop.body)} statements in body")
    
    # Look through the While loop body to find the If statement we want
    for i, stmt in enumerate(while_loop.body):
        print(f"\nWhile body statement {i}: {type(stmt).__name__}")
        if isinstance(stmt, ast.If):
            print(f"  Found If statement at index {i}")
            test = stmt.test
            print(f"  If test type: {type(test).__name__}")
            print(f"  If test dump: {ast.dump(test)}")
            
            # Check if it's a BoolOp with Or
            if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or):
                print(f"  This is a BoolOp Or!")
                print(f"  Number of values: {len(test.values)}")
                for j, val in enumerate(test.values):
                    print(f"    Value {j}: {ast.dump(val)}")
                    # Check if it's "prev_ts is None"
                    if isinstance(val, ast.Compare):
                        print(f"      Is Compare")
                        print(f"      Left: {ast.dump(val.left) if hasattr(val, 'left') else 'N/A'}")
                        print(f"      Ops: {ast.dump(val.ops) if hasattr(val, 'ops') else 'N/A'}")
                        print(f"      Comparators: {ast.dump(val.comparators) if hasattr(val, 'comparators') else 'N/A'}")
                        
                        # Check if it's "prev_ts is None"
                        if (hasattr(val, 'left') and isinstance(val.left, ast.Name) and val.left.id == 'prev_ts' and
                            len(val.ops) == 1 and isinstance(val.ops[0], ast.Is) and
                            len(val.comparators) == 1 and isinstance(val.comparators[0], ast.Constant) and val.comparators[0].value is None):
                            print(f"      >>> This is 'prev_ts is None'")
                            
                    # Check if it's "prev_ts < gen_start" or "prev_ts <= gen_start" or "prev_ts >= gen_start" etc.
                    elif (hasattr(val, 'left') and isinstance(val.left, ast.Name) and val.left.id == 'prev_ts' and
                          len(val.ops) == 1 and isinstance(val.ops[0], (ast.Lt, ast.LtE, ast.Gt, ast.GtE)) and
                          len(val.comparators) == 1 and isinstance(val.comparators[0], ast.Name) and val.comparators[0].id == 'gen_start'):
                        print(f"      >>> This is a comparison with gen_start: {ast.dump(val.ops[0])}")
else:
    print("While loop not found")
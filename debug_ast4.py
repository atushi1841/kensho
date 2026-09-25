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

# Find the While loop
while_loop = None
for stmt in fn_node.body:
    if isinstance(stmt, ast.While):
        while_loop = stmt
        break

if while_loop:
    print(f"\nFound While loop")
    
    # Look for the If statement that checks line.startswith("[PROXY-CHECK]")
    proxy_check_if = None
    for stmt in while_loop.body:
        if isinstance(stmt, ast.If):
            # Check if this is the line.startswith check
            test = stmt.test
            if (isinstance(test, ast.Call) and 
                isinstance(test.func, ast.Attribute) and
                test.func.attr == 'startswith' and
                len(test.args) == 1 and
                isinstance(test.args[0], ast.Constant) and
                test.args[0].value == "[PROXY-CHECK]"):
                proxy_check_if = stmt
                print(f"Found line.startswith If statement")
                break
    
    if proxy_check_if:
        print(f"The If statement has {len(proxy_check_if.body)} statements in body")
        
        # Now look through the body of this if statement to find the timestamp check if
        for i, stmt in enumerate(proxy_check_if.body):
            print(f"\nProxy check if body statement {i}: {type(stmt).__name__}")
            if isinstance(stmt, ast.Assign):
                # Look for assignments like prev_ts = None or j = i - 1
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        print(f"  Assignment: {target.id} = ...")
            elif isinstance(stmt, ast.While):
                print(f"  Found inner While loop (timestamp search)")
                # Look through the while loop body
                for j, while_stmt in enumerate(stmt.body):
                    print(f"    While body {j}: {type(while_stmt).__name__}")
                    if isinstance(while_stmt, ast.Assign):
                        for target in while_stmt.targets:
                            if isinstance(target, ast.Name):
                                print(f"      Assignment: {target.id} = ...")
                    elif isinstance(while_stmt, ast.If):
                        print(f"      Found If inside While (regex match check)")
                        # This is the if m: statement
            elif isinstance(stmt, ast.If):
                print(f"  Found If statement after While loop - THIS IS THE ONE WE WANT!")
                # This should be the if prev_ts is None or prev_ts < gen_start: statement
                test = stmt.test
                print(f"    If test type: {type(test).__name__}")
                print(f"    If test dump: {ast.dump(test)}")
                
                # Check if it's the BoolOp Or we're looking for
                if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or):
                    print(f"    This is a BoolOp Or!")
                    print(f"    Number of values: {len(test.values)}")
                    for j, val in enumerate(test.values):
                        print(f"      Value {j}: {ast.dump(val)}")
                        # Check each part
                        if isinstance(val, ast.Compare):
                            print(f"        Is Compare")
                            print(f"        Left: {ast.dump(val.left) if hasattr(val, 'left') else 'N/A'}")
                            print(f"        Ops: {ast.dump(val.ops) if hasattr(val, 'ops') else 'N/A'}")
                            print(f"        Comparators: {ast.dump(val.comparators) if hasattr(val, 'comparators') else 'N/A'}")
                            
                            # Check for "prev_ts is None"
                            if (hasattr(val, 'left') and isinstance(val.left, ast.Name) and val.left.id == 'prev_ts' and
                                len(val.ops) == 1 and isinstance(val.ops[0], ast.Is) and
                                len(val.comparators) == 1 and isinstance(val.comparators[0], ast.Constant) and val.comparators[0].value is None):
                                print(f"        >>> This is 'prev_ts is None'")
                                
                            # Check for comparison with gen_start
                            elif (hasattr(val, 'left') and isinstance(val.left, ast.Name) and val.left.id == 'prev_ts' and
                                  len(val.ops) == 1 and isinstance(val.ops[0], (ast.Lt, ast.LtE, ast.Gt, ast.GtE)) and
                                  len(val.comparators) == 1 and isinstance(val.comparators[0], ast.Name) and val.comparators[0].id == 'gen_start'):
                                op_name = {ast.Lt: '<', ast.LtE: '<=', ast.Gt: '>', ast.GtE: '>='}[type(val.ops[0])]
                                print(f"        >>> This is 'prev_ts {op_name} gen_start'")
                else:
                    print(f"    This is NOT a BoolOp Or - it's {type(test).__name__}")
else:
    print("While loop not found")
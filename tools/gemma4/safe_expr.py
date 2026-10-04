import ast,json


def strict_json(raw):
 def pairs(items):
  result={}
  for k,v in items:
   if k in result: raise ValueError("duplicate key")
   result[k]=v
  return result
 def bad(_): raise ValueError("nonfinite")
 return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)

def same(a,b):
 return type(a) is type(b) and (all(k in a and same(a[k],v) for k,v in b.items()) and len(a)==len(b) if isinstance(b,dict) else all(same(x,y) for x,y in zip(a,b)) and len(a)==len(b) if isinstance(b,list) else a==b)

OPS = {ast.Add:lambda a,b:a+b, ast.Sub:lambda a,b:a-b,
       ast.Mult:lambda a,b:a*b, ast.Mod:lambda a,b:a%b}

CMPS = {ast.Eq:lambda a,b:a==b, ast.NotEq:lambda a,b:a!=b,
        ast.Lt:lambda a,b:a<b, ast.LtE:lambda a,b:a<=b,
        ast.Gt:lambda a,b:a>b, ast.GtE:lambda a,b:a>=b}

def expression(node, env, execute):
 # Validate every branch first; then interpret only allowed nodes. No exec/eval.
 def sub(n): return expression(n,env,execute)
 if isinstance(node,ast.Constant):
  if type(node.value) not in (int,bool) or abs(node.value)>1000000: raise ValueError("constant")
  out=node.value
 elif isinstance(node,ast.Name) and node.id in env: out=env[node.id]
 elif isinstance(node,ast.BinOp) and (type(node.op) in OPS or isinstance(node.op,ast.FloorDiv)):
  a,b=sub(node.left),sub(node.right)
  out=(a//b if isinstance(node.op,ast.FloorDiv) else OPS[type(node.op)](a,b)) if execute else 0
 elif isinstance(node,ast.UnaryOp) and type(node.op) in (ast.Not,ast.USub,ast.UAdd):
  a=sub(node.operand); out=(not a) if isinstance(node.op,ast.Not) else -a if isinstance(node.op,ast.USub) else +a
 elif isinstance(node,ast.BoolOp) and type(node.op) in (ast.And,ast.Or):
  out=sub(node.values[0])
  for n in node.values[1:]:
   if not execute or (bool(out) if isinstance(node.op,ast.And) else not bool(out)): out=sub(n)
 elif isinstance(node,ast.Compare) and all(type(o) in CMPS for o in node.ops):
  left=sub(node.left)
  out=True
  for op,right_node in zip(node.ops,node.comparators):
   right=sub(right_node)
   if execute and not CMPS[type(op)](left,right):
    out=False
    break
   left=right
 elif isinstance(node,ast.IfExp):
  condition=sub(node.test)
  if execute: out=sub(node.body if condition else node.orelse)
  else: sub(node.body); sub(node.orelse); out=0
 else: raise ValueError("forbidden AST")
 if type(out) not in (int,bool) or abs(out)>1000000: raise ValueError("bound")
 return out

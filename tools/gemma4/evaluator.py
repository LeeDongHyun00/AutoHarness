"""Offline owner-side scoring. Provide case/oracle explicitly from evaluator-authorized storage."""
import ast,json,math
from jsonschema import Draft202012Validator
from safe_expr import strict_json,same,expression
def schema_same(a,b,schema):
 """JSON-schema value equivalence, without weakening Python code-test types."""
 if not Draft202012Validator(schema).is_valid(a):return False
 if type(a) is bool or type(b) is bool:return type(a) is type(b) and a==b
 types=schema.get('type',[])
 if isinstance(types,str):types=[types]
 if any(t in types for t in ('number','integer')) and type(a) in (int,float) and type(b) in (int,float):
  return (type(a) is int or math.isfinite(a)) and (type(b) is int or math.isfinite(b)) and a==b
 if isinstance(a,dict) and isinstance(b,dict):
  return set(a)==set(b) and all(schema_same(a[k],b[k],schema.get('properties',{}).get(k,{})) for k in b)
 if isinstance(a,list) and isinstance(b,list):
  return len(a)==len(b) and all(schema_same(x,y,schema.get('items',{})) for x,y in zip(a,b))
 return same(a,b)

class ContractViolation(ValueError):pass
class ValidatorLimit(ValueError):pass

def evaluate_code(raw,spec):
 out={'ast_allowed':None,'ast_failure_class':None,'code_function':None,'tests_passed':0,'tests_total':len(spec['cases']),'execution':'restricted_AST_interpreter_only'}
 try:
  if not isinstance(raw,str):raise ContractViolation('code_not_string')
  if len(raw)>4000:raise ValidatorLimit('source_length_limit')
  tree=ast.parse(raw)
  if len(list(ast.walk(tree)))>120:raise ValidatorLimit('node_limit')
  if len(tree.body)!=1:raise ContractViolation('one_function_required')
  f=tree.body[0]
  if not isinstance(f,ast.FunctionDef) or f.name!=spec['name'] or f.decorator_list or f.returns or getattr(f,'type_params',[]):raise ContractViolation('function')
  a=f.args
  if a.posonlyargs or a.vararg or a.kwarg or a.kwonlyargs or a.defaults or a.kw_defaults:raise ContractViolation('signature')
  if [x.arg for x in a.args]!=spec['args'] or any(x.annotation for x in a.args):raise ContractViolation('signature')
  if len(f.body)!=1 or not isinstance(f.body[0],ast.Return):raise ContractViolation('body')
  expr=f.body[0].value
  allowed=(ast.Constant,ast.Name,ast.Load,ast.BinOp,ast.UnaryOp,ast.BoolOp,ast.Compare,ast.IfExp,
           ast.Add,ast.Sub,ast.Mult,ast.FloorDiv,ast.Mod,ast.Not,ast.USub,ast.UAdd,ast.And,ast.Or,
           ast.Eq,ast.NotEq,ast.Lt,ast.LtE,ast.Gt,ast.GtE)
  for node in ast.walk(expr):
   if not isinstance(node,allowed):raise ContractViolation('forbidden_AST_'+type(node).__name__)
   if isinstance(node,ast.Name) and node.id not in spec['args']:raise ContractViolation('unknown_name')
   if isinstance(node,ast.Constant) and (type(node.value) not in (int,bool) or abs(node.value)>1000000):raise ContractViolation('constant_contract')
  expression(expr,dict.fromkeys(spec['args'],1),False)
  out['ast_allowed']=True
  for inputs,expected in spec['cases']:
   try:out['tests_passed']+=same(expression(expr,dict(zip(spec['args'],inputs)),True),expected)
   except (ValueError,ZeroDivisionError,OverflowError,RecursionError):pass
  out['code_function']=out['tests_passed']/out['tests_total']
 except (SyntaxError,ContractViolation) as exc:
  out.update(ast_allowed=False,ast_failure_class='contract_violation',ast_error=str(exc)[:150])
 except (ValidatorLimit,RecursionError,OverflowError,MemoryError) as exc:
  out.update(ast_allowed=None,ast_failure_class='validator_limit',ast_error=type(exc).__name__)
 except (ValueError,TypeError,NotImplementedError) as exc:
  out.update(ast_allowed=None,ast_failure_class='validator_unsupported',ast_error=type(exc).__name__)
 return out

def grade(case,oracle,raw,status='completed',finish_reason='stop'):
 cid=case['case_id']
 out={'case_id':cid,'status':status,'finish_reason':finish_reason,'truncated':finish_reason in ('length','max_tokens'),
      'json_syntax':None,'json_schema':None,'korean_meaning':None,'semantic_exact':None,'evidence':None,
      'ast_allowed':None,'ast_failure_class':None,'code_function':None,'harness_structure':None,'harness_usefulness':None,'review_required':False,'assessment_scope':{'suite':'caller_supplied_cases','code':'restricted_AST_interpreter','mutation':'contract_reasoning_only','harness':'plan_generation_only','downstream_execution':'not_run'}}
 if status!='completed':return out
 if not isinstance(raw,str) or len(raw)>16000:
  out['json_syntax']=False;out['format_error']='output_size_or_type';return out
 try:obj=strict_json(raw);out['json_syntax']=True
 except (ValueError,TypeError,RecursionError):
  out['json_syntax']=False;out['format_error']='invalid_json';return out
 out['json_schema']=Draft202012Validator(case['response_schema']).is_valid(obj)
 if not out['json_schema']:
  out['format_error']='schema_mismatch';return out
 kind=oracle['kind']
 if kind=='exact':out['semantic_exact']=float(schema_same(obj,oracle['expected'],case['response_schema']))
 elif kind=='evidence':
  out['evidence']=float(same(obj['evidence'],oracle['expected']['evidence']))
  out['semantic_exact']=float(all(schema_same(obj[k],v,case['response_schema']['properties'][k]) for k,v in oracle['expected'].items() if k!='evidence'))
 elif kind=='code':out.update(evaluate_code(obj['code'],oracle['tests']))
 elif kind=='harness':
  steps=obj['plan'];mapping=oracle['path_evidence']
  checks={'paths_grounded':all(s['path'] in mapping for s in steps),
          'paths_covered':set(s['path'] for s in steps)==set(mapping),
          'evidence_grounded':all(s['path'] in mapping and s['evidence']==[mapping[s['path']]] for s in steps),
          'commands_grounded':obj['commands']==oracle['allowed_commands'],
          'actions_nonempty':all(bool(s['action'].strip()) for s in steps),
          'stop_nonempty':bool(obj['stop_conditions']) and all(bool(s.strip()) for s in obj['stop_conditions'])}
  out['harness_structure']=sum(checks.values())/len(checks);out['structural_checks']=checks
  out['evidence']=float(checks['evidence_grounded']);out['review_required']=True
 elif kind=='review':out['review_required']=True
 return out

def summarize(results,plan):
 """Separate denominators; no composite capability score, no imputation of failed runs."""
 indexed={r['request_id']:r for r in results}
 if len(indexed)!=len(results):raise ValueError('duplicate result IDs')
 planned={r['request_id'] for r in plan['requests']}
 if not set(indexed)<=planned:raise ValueError('unplanned result')
 groups=[]
 for split in ['development','evaluation']:
  for domain in sorted({x['domain'] for x in plan['requests']}):
   for variant in 'ABC':
    cells=[x for x in plan['requests'] if (x['split'],x['domain'],x['variant'])==(split,domain,variant)]
    rs=[indexed[c['request_id']] for c in cells if c['request_id'] in indexed]
    record={'split':split,'domain':domain,'variant':variant,'planned':len(cells),'recorded':len(rs),'completed':sum(r['status']=='completed' for r in rs)}
    for metric in ['json_syntax','json_schema','semantic_exact','evidence','code_function','harness_structure','harness_usefulness','korean_meaning']:
     vals=[float(r[metric]) for r in rs if r.get(metric) is not None]
     record[metric]={'n':len(vals),'mean':sum(vals)/len(vals) if vals else None}
    code_cells=[c for c in cells if c['kind']=='code']
    code_rows=[indexed[c['request_id']] for c in code_cells if c['request_id'] in indexed]
    if code_cells:
     passed=sum(r.get('ast_allowed') is True for r in code_rows)
     failed=sum(r.get('ast_allowed') is False for r in code_rows)
     unknown=len(code_cells)-passed-failed
     known_failure=sum(r['status']=='completed' and (r.get('json_syntax') is False or r.get('json_schema') is False or r.get('ast_allowed') is False or (r.get('code_function') is not None and r['code_function']<1)) for r in code_rows)
     suite_success=sum(r.get('ast_allowed') is True and r.get('code_function')==1 for r in code_rows)
     judged=known_failure+suite_success
     record['code_denominators']={'planned':len(code_cells),'ast_pass':passed,'ast_fail':failed,'ast_unassessed':unknown,
      'ast_failure_rate_among_checked':failed/(passed+failed) if passed+failed else None,
      'contract_violations':sum(r.get('ast_failure_class')=='contract_violation' for r in code_rows),
      'validator_limits':sum(r.get('ast_failure_class') in ('validator_limit','validator_unsupported') for r in code_rows),
      'suite_success':suite_success,'known_failure':known_failure,'unassessed':len(code_cells)-judged,
      'failure_rate_among_adjudicated':known_failure/judged if judged else None,
      'failure_rate_lower_bound_all_planned':known_failure/len(code_cells),
      'failure_rate_upper_bound_all_planned':(len(code_cells)-suite_success)/len(code_cells)}
    groups.append(record)
 return {'groups':groups,'independent_unit':'family','family_count':len({r['family_id'] for r in plan['requests']}),'warning':'No pooled capability score. Schema failures have unassessed semantics, not semantic success. Report format and operational coverage alongside conditional semantic rates.'}

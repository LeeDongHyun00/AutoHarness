"""Prepared local-only inference runner. Not executed during package preparation."""
import argparse,fcntl,hashlib,json,os,time,urllib.request,platform,subprocess
from pathlib import Path

def sha(b):return hashlib.sha256(b).hexdigest()
def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def atomic(p,x):
 tmp=p.with_suffix('.tmp')
 with tmp.open('w') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
 os.replace(tmp,p)
 fd=os.open(str(p.parent),os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
# Ignore external proxy settings for this explicitly authorized localhost-only route.
# No external hosts, auth keys, model downloads, generated shell, or generated Python.
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
BASE='http://127.0.0.1:18090'
def api(path,body=None):
 if path not in ['/apply-template','/tokenize','/v1/chat/completions','/lora-adapters','/v1/chat/completions/input_tokens']:raise ValueError('endpoint')
 req=urllib.request.Request(BASE+path,data=None if body is None else canon(body),headers={'Content-Type':'application/json'})
 with OPENER.open(req,timeout=300) as r:return json.load(r)

def runtime_metadata():
 info={'platform':'kaggle' if Path('/kaggle/working').exists() else 'colab' if Path('/content').exists() else 'other',
       'python':platform.python_version(),'system':platform.system(),'recorded_unix':time.time(),'gpu':None}
 try:
  info['gpu']=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader'],text=True,timeout=10).strip()
 except (OSError,subprocess.SubprocessError):info['gpu']='unavailable'
 return info

def run(payload_path,out,include_evaluation=False,confirm_runtime=False,call=api,preflight_only=False):
 payload_path=Path(payload_path);raw=payload_path.read_bytes();pack=json.loads(raw)
 if not confirm_runtime:raise ValueError('Confirm pinned model revision, b11382, no LoRA, context4096 and fixed chat/thinking settings first')
 cells=[r for r in pack['requests'] if r['split']=='development' or include_evaluation]
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 with (out/'run.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  statefile=out/'checkpoint.json'
  if statefile.exists():
   state=json.loads(statefile.read_text())
   if state['payload_sha256']!=sha(raw):raise ValueError('Payload changed; refuse resume')
  else:
   state={'payload_sha256':sha(raw),'model':pack['model'],'runtime_confirmed_by_operator':True,'preflight':{},'records':{}}
   atomic(statefile,state)
  runtime_lock=out/'runtime-lock.json'
  if not runtime_lock.is_file():raise ValueError('runtime-lock.json required before preflight')
  lock_value=json.loads(runtime_lock.read_text())
  expected={'repo':pack['model']['repo'],'revision':pack['model']['revision'],'llama_commit':pack['model']['llama_cpp_commit'],
            'context':4096,'lora':[],'thinking':False,'reasoning_budget':0,'chat_template_kwargs':{'enable_thinking':False}}
  for key,value in expected.items():
   if lock_value.get(key)!=value:raise ValueError('Runtime setting mismatch: '+key)
  version=lock_value.get('server_version','')
  if '11382' not in version or '11fe02151' not in version:raise ValueError('Engine build mismatch')
  for key in ['model_sha256','server_sha256']:
   value=lock_value.get(key,'')
   if len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ValueError('Missing binary/model hash')
  if 'runtime_lock' in state and state['runtime_lock']!=lock_value:raise ValueError('Runtime lock changed; refuse resume')
  state['runtime_lock']=lock_value
  state.setdefault('sessions',[]).append(runtime_metadata())
  atomic(statefile,state)
  adapters=call('/lora-adapters')
  if not isinstance(adapters,list) or adapters:raise ValueError('Require no loaded LoRA adapters for base-only experiment')
  # Preflight all selected inputs before sending any generation request.
  for cell in cells:
   rid=cell['request_id'];req=cell['request'];expected=cell['request_sha256']
   if sha(canon(req))!=expected:raise ValueError('Request hash mismatch')
   if req.get('chat_template_kwargs')!={'enable_thinking':False}:raise ValueError('Thinking must be disabled explicitly')
   templated=call('/apply-template',req)
   prompt=templated.get('prompt')
   if not isinstance(prompt,str):raise ValueError('/apply-template must return prompt; no approximate fallback')
   tokens=call('/tokenize',{'content':prompt,'add_special':True,'parse_special':True}).get('tokens')
   if not isinstance(tokens,list) or any(type(t) is not int for t in tokens):raise ValueError('/tokenize response')
   count=call('/v1/chat/completions/input_tokens',req).get('input_tokens')
   if type(count) is not int or count!=len(tokens):raise ValueError('Template/tokenize differs from actual chat input token count')
   if len(tokens)+req['max_tokens']+8>4096:raise ValueError('Context budget exceeded: '+rid)
   checked={'prompt_tokens':len(tokens),'token_ids':tokens,'rendered_prompt_sha256':sha(prompt.encode()),'chat_input_tokens':count,'settings':{'enable_thinking':False,'add_special':True,'parse_special':True}}
   if rid in state['preflight'] and state['preflight'][rid]!=checked:raise ValueError('Rendered template/tokenizer changed; refuse resume')
   state['preflight'][rid]=checked
   atomic(statefile,state)
  if preflight_only:return state
  for cell in cells:
   rid=cell['request_id']
   if rid in state['records']:
    if state['records'][rid]['status']=='completed':continue
    raise ValueError('Unresolved prior request; manual review required: '+rid)
   rec={'request_id':rid,'case_id':cell['case_id'],'split':cell['split'],'variant':cell['variant'],'request_sha256':cell['request_sha256'],'status':'reserved','started_unix':time.time()}
   state['records'][rid]=rec;atomic(statefile,state)
   try:
    response=call('/v1/chat/completions',cell['request'])
    choice=response['choices'][0];message=choice['message'];text=message.get('content')
    if not isinstance(text,str):raise ValueError('Missing string content')
    rec.update(status='completed',raw_text=text,reasoning_content=message.get('reasoning_content'),finish_reason=choice.get('finish_reason'),usage=response.get('usage'),seconds=time.time()-rec['started_unix'])
    atomic(statefile,state)
    print(rid,rec['finish_reason'],flush=True)
    observed=(response.get('usage') or {}).get('prompt_tokens')
    if observed is not None and observed!=state['preflight'][rid]['prompt_tokens']:
     rec['protocol_mismatch']='prompt_tokens';atomic(statefile,state);raise ValueError('Observed generation token count differs from preflight')
   except Exception as exc:
    rec.update(status='completed_protocol_mismatch' if rec.get('protocol_mismatch') else 'infrastructure_failed',error_type=type(exc).__name__,seconds=time.time()-rec['started_unix'])
    atomic(statefile,state);raise
 return state
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--payload',required=True);p.add_argument('--out',required=True);p.add_argument('--include-evaluation',action='store_true');p.add_argument('--confirm-runtime',action='store_true');p.add_argument('--preflight-only',action='store_true');a=p.parse_args()
 run(a.payload,a.out,a.include_evaluation,a.confirm_runtime,preflight_only=a.preflight_only)

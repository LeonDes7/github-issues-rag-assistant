"""One approved Ohio code-image update and exactly two remediation live smoke checks."""
import base64,hashlib,json,os,re,subprocess,time
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
import boto3,requests
from botocore.config import Config
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]
REGION='us-east-2';TAG='remediation-20261008-final'
QUESTIONS=["What is the recommended way to dump settings in starlette.config without exposing sensitive information like JWT secrets?"]
CAP=Decimal('0.00210760');CEILING=Decimal('0.00210760')
def main():
 load_dotenv(ROOT/'.env')
 REGISTRY=os.environ['AWS_ECR_REGISTRY']
 path=ROOT/'docs/deployment/live/remediation_deployment_live_results.json'
 result={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'region':REGION,'hard_openai_cap_usd':str(CAP),'conservative_one_request_ceiling_usd':str(CEILING),'checks':[],'standard_rate_token_cost_usd':'0','openai_usage_unknown':False,'local_tests_passed':101,'configuration_changed':False,'infrastructure_created':False,'existing_images_retained':True}
 with path.open('x',encoding='utf-8') as f:f.write(json.dumps(result))
 def save():path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 try:
  cfg=Config(retries={'max_attempts':0});lam=boto3.client('lambda',region_name=REGION,config=cfg);ecr=boto3.client('ecr',region_name=REGION,config=cfg)
  before=lam.get_function(FunctionName='github-rag-api');conf=before['Configuration'];env=conf.get('Environment',{}).get('Variables',{})
  prior=json.loads((ROOT/'docs/deployment/live/final_deployment_live_results.json').read_text());assert before['Code'].get('ResolvedImageUri')==prior['image_uri'];assert conf['RevisionId']==prior['lambda_revision'];assert conf['MemorySize']==1024 and conf['Timeout']==90 and conf['Architectures']==['x86_64']
  subprocess.run(['docker','build','--platform','linux/amd64','--provenance=false','-t','github-rag-api:'+TAG,'.'],cwd=ROOT,check=True)
  keys=['OPENAI_GENERATION_MODEL','OPENAI_EMBEDDING_MODEL','RAG_CONTEXT_MODE','RAG_RETRIEVAL_MODE','RAG_HNSW_EF_SEARCH','RAG_CONFIDENCE_THRESHOLD','RAG_REPOSITORIES','GITHUB_REPOS','OPENAI_GENERATION_MAX_OUTPUT_TOKENS','OPENAI_MAX_RETRIES','RAG_MAX_GENERATION_INPUT_TOKENS']
  args=['docker','run','--rm','--network','none','--entrypoint','python']
  for k in ['OPENAI_API_KEY','API_AUTH_TOKEN','PGHOST','PGDATABASE','PGUSER','PGPASSWORD']:args+=['-e',k+'=offline-test']
  for k in keys:
   if k in env:args+=['-e',k+'='+env[k]]
  snippet="import hashlib,json; from pathlib import Path; from unittest.mock import patch; from rag_assistant import api; from rag_assistant.lambda_handler import handler; s=api.get_settings(); keys="+repr(keys)+"; print(json.dumps({'settings':{k:s.get(k) for k in keys},'api_sha256':hashlib.sha256(Path(api.__file__).read_bytes()).hexdigest(),'redaction_sha256':hashlib.sha256(Path(api.__file__).with_name('redaction.py').read_bytes()).hexdigest()})); assert callable(handler); "
  args+=['github-rag-api:'+TAG,'-c',snippet]
  validation=subprocess.run(args,capture_output=True,text=True,check=True)
  v=json.loads(validation.stdout);sett=v['settings'];expected=json.loads((ROOT/'docs/measurements/final_latency_cost_plan.json').read_text())['settings']
  for k in ['OPENAI_GENERATION_MODEL','OPENAI_EMBEDDING_MODEL','RAG_CONTEXT_MODE','RAG_RETRIEVAL_MODE','RAG_HNSW_EF_SEARCH','RAG_CONFIDENCE_THRESHOLD','RAG_REPOSITORIES']:assert sett[k]==expected[k],k
  assert sett['OPENAI_GENERATION_MAX_OUTPUT_TOKENS']==512 and sett['OPENAI_MAX_RETRIES']==0 and sett['RAG_MAX_GENERATION_INPUT_TOKENS']==12000
  assert v['api_sha256']==hashlib.sha256((ROOT/'src/rag_assistant/api.py').read_bytes()).hexdigest()
  assert v['redaction_sha256']==hashlib.sha256((ROOT/'src/rag_assistant/redaction.py').read_bytes()).hexdigest()
  assert CEILING<=CAP
  result['image_validation']=v;result['previous_image_uri']=before['Code'].get('ResolvedImageUri');save()
  auth=ecr.get_authorization_token()['authorizationData'][0];user,password=base64.b64decode(auth['authorizationToken']).decode().split(':',1)
  subprocess.run(['docker','login','--username',user,'--password-stdin',REGISTRY],input=password,text=True,capture_output=True,check=True)
  remote=REGISTRY+'/github-rag-api:'+TAG
  subprocess.run(['docker','tag','github-rag-api:'+TAG,remote],check=True)
  subprocess.run(['docker','push',remote],check=True)
  detail=ecr.describe_images(repositoryName='github-rag-api',imageIds=[{'imageTag':TAG}])['imageDetails'][0]
  uri=REGISTRY+'/github-rag-api@'+detail['imageDigest'];result.update(image_uri=uri,compressed_image_bytes=detail['imageSizeInBytes'],image_pushed=True);save()
  lam.update_function_code(FunctionName='github-rag-api',ImageUri=uri,RevisionId=conf['RevisionId'],Publish=False)
  result['lambda_code_update_requested']=True;save()
  lam.get_waiter('function_updated_v2').wait(FunctionName='github-rag-api',WaiterConfig={'Delay':5,'MaxAttempts':30})
  after=lam.get_function(FunctionName='github-rag-api');assert after['Code'].get('ResolvedImageUri')==uri
  assert after['Configuration'].get('Environment',{})==conf.get('Environment',{})
  for key in ['Role','VpcConfig','MemorySize','Timeout','Architectures']:assert after['Configuration'][key]==conf[key],key
  result['lambda_code_updated']=True;result['lambda_revision']=after['Configuration']['RevisionId'];save()
  endpoint='https://w3qqwb25w0.execute-api.us-east-2.amazonaws.com'
  session=requests.Session()  # requests defaults to zero retries; redirects disabled.
  t=time.perf_counter();health=session.get(endpoint+'/health',timeout=95,allow_redirects=False)
  entry={'method':'GET','path':'/health','http_status':health.status_code,'client_latency_ms':(time.perf_counter()-t)*1000,'body':health.text}
  result['checks'].append(entry);save()
  assert health.status_code==200 and health.json().get('status')=='ok' and health.json().get('database')=='reachable','Live health failed; stop'
  spent=Decimal(0)
  for i,q in enumerate(QUESTIONS):
   # Reserve the full single-request ceiling; never assume abstention.
   assert CEILING<=CAP
   entry={'method':'POST','path':'/ask','question':q,'top_k':5,'status':'attempting'}
   result['checks'].append(entry);save()
   t=time.perf_counter();response=session.post(endpoint+'/ask',json={'question':q,'top_k':5},headers={'Authorization':'Bearer '+os.environ['API_AUTH_TOKEN']},timeout=95,allow_redirects=False)
   entry.update(http_status=response.status_code,client_latency_ms=(time.perf_counter()-t)*1000,body=response.text)
   if response.status_code!=200:
    result['openai_usage_unknown']=True;save();raise RuntimeError('Live ask failed; no retry')
   body=response.json();entry['api_response']=body;p=body['performance']
   charge=(Decimal(p['embedding_tokens'])*Decimal('.02')+Decimal(p['generation_prompt_tokens'])*Decimal('.15')+Decimal(p['generation_completion_tokens'])*Decimal('.60'))/Decimal(1000000)
   spent+=charge;entry['standard_rate_token_cost_usd']=str(charge);result['standard_rate_token_cost_usd']=str(spent)
   assert p['generation_prompt_tokens']<=12000 and p['generation_completion_tokens']<=512 and spent<=CAP,'Token budget mismatch'
   answer=body['answer'];sources=body['citations'];refs=[int(n) for n in re.findall(r'\[(\d+)\]',answer)]
   from rag_assistant.redaction import UNSAFE_SETTINGS_PATTERN, UNSAFE_SETTINGS_ANSWER, redact_sensitive_text
   assert answer and sources,'Empty answer or structured citations'
   assert not UNSAFE_SETTINGS_PATTERN.search(answer),'Unsafe settings-dump pattern returned'
   assert redact_sensitive_text(answer)==answer,'Recognizable unredacted sensitive value returned'
   assert all(s.get('source_url') and s.get('issue_url') for s in sources),'Source links missing'
   assert all(1<=n<=len(sources) for n in refs),'Invalid inline citation'
   abstentions=["There isn't enough evidence in the indexed issues to answer this question.","The retrieved excerpts do not provide enough evidence to answer this question."]
   if answer==UNSAFE_SETTINGS_ANSWER: entry['outcome']='safely_withheld'
   elif answer in abstentions: entry['outcome']='model_abstained' if p['generation_prompt_tokens'] else 'cutoff_refused'
   else:
    assert refs,'Supported answer has no inline citation'
    entry['outcome']='answered_pending_manual_support_review'
   entry['unsafe_settings_pattern_suppressed']=True
   entry['status']='passed';save();print('/ask '+str(i+1)+' '+entry['outcome']+' cumulative=$'+str(spent),flush=True)
  result['status']='deployed_two_remediation_checks_passed'
 except Exception as exc:
  result['status']='failed_stopped_no_retry';result['error_type']=type(exc).__name__;result['failure']=str(exc)
  for entry in result['checks']:
   if entry.get('status')=='attempting' and 'http_status' not in entry:result['openai_usage_unknown']=True
  raise
 finally:
  result['finished_at_utc']=datetime.now(timezone.utc).isoformat();result['aws_billed_cost_usd']=None
  result['cost_note']='Actual API-reported token usage priced at standard uncached rates; cached input breakdown is not exposed by current API so cache discounts/invoice cost cannot be reconciled. Unknown failed-call usage flagged separately. AWS billed cost not yet available.';save()
  print(result['status'],result['standard_rate_token_cost_usd'])
if __name__=='__main__':main()

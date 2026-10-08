"""Exactly one approved live ask; no retry or deployment."""
import json,os,re,time
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import requests
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]
plan=json.loads((ROOT/'docs/deployment/preflights/safe_answer_live_cost_preflight.json').read_text())
path=ROOT/'docs/deployment/live/safe_answer_live_results.json'
r={'status':'prepared','started_at_utc':datetime.now(timezone.utc).isoformat(),'hard_openai_cap_usd':'0.00210756','request_count':0,'retries':0,'plan':plan,'actual_token_cost_usd':None,'openai_usage_unknown':False}
with path.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2)
def save():path.write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
try:
 load_dotenv(ROOT/'.env')
 token=os.environ['API_AUTH_TOKEN']
 ceiling=(D(18)*D('.02')+D(12000)*D('.15')+D(512)*D('.60'))/D(1000000)
 assert ceiling<=D(r['hard_openai_cap_usd'])
 assert plan['request_count']==1 and plan['retries']==0
 session=requests.Session()
 session.mount('https://',requests.adapters.HTTPAdapter(max_retries=0))
 r['status']='attempting';r['request_count']=1;r['openai_usage_unknown']=True;save()
 start=time.perf_counter()
 response=session.post(plan['endpoint'],json=plan['body'],headers={'Authorization':'Bearer '+token},timeout=95,allow_redirects=False)
 r.update(http_status=response.status_code,client_latency_ms=(time.perf_counter()-start)*1000,raw_response=response.text);save()
 assert response.status_code==200,'Live request failed; no retry'
 body=response.json();r['api_response']=body;save()
 p=body['performance']
 charge=(D(p['embedding_tokens'])*D('.02')+D(p['generation_prompt_tokens'])*D('.15')+D(p['generation_completion_tokens'])*D('.60'))/D(1000000)
 r['actual_token_cost_usd']=str(charge);r['openai_usage_unknown']=False;save()
 assert p['embedding_tokens']<=18 and p['generation_prompt_tokens']<=12000 and p['generation_completion_tokens']<=512 and charge<=ceiling,'Token bound mismatch'
 answer=body['answer'];sources=body['citations'];refs=[int(n) for n in re.findall(r'\[(\d+)\]',answer)]
 from rag_assistant.redaction import UNSAFE_SETTINGS_PATTERN,UNSAFE_SETTINGS_ANSWER,redact_sensitive_text
 fixed=["The retrieved excerpts do not provide enough evidence to answer this question.","There isn't enough evidence in the indexed issues to answer this question.",UNSAFE_SETTINGS_ANSWER]
 r['outcome']='abstained_or_withheld' if answer in fixed else 'answered'
 assert answer not in fixed,'Supported answer not verified: abstained/withheld'
 assert sources and refs and all(1<=i<=len(sources) for i in refs),'Missing/invalid citations'
 assert any(sources[i-1]['repository']=='tiangolo/fastapi' and sources[i-1]['issue_number']==2071 for i in refs),'Expected source not cited'
 assert re.search(r'disconnect',answer,re.I) and re.search(r'larger|large',answer,re.I) and re.search(r'frame',answer,re.I),'Expected supported fact missing'
 assert not UNSAFE_SETTINGS_PATTERN.search(answer) and redact_sensitive_text(answer)==answer,'Unsafe/sensitive output'
 assert all(s.get('source_url') and s.get('issue_url') for s in sources),'Missing structured source links'
 r['status']='passed';r['support_review']='Returned fact matches manually verified case and prior local source-grounded answers: larger base64 video frames disconnected the WebSocket client.'
except Exception as exc:
 r['status']='failed_stopped_no_retry';r['failure_type']=type(exc).__name__;r['failure']=str(exc)
finally:
 r['finished_at_utc']=datetime.now(timezone.utc).isoformat();r['aws_billed_cost_usd']=None;r['cost_note']='API token usage priced at standard uncached rates; cached billing breakdown and AWS actual billed cost are unavailable.';save()
 print(json.dumps({'status':r['status'],'cost':r['actual_token_cost_usd'],'outcome':r.get('outcome'),'failure':r.get('failure')}))

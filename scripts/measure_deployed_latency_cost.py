"""Measure deployed latency and cost; preview offline or explicitly execute a fresh run."""
import argparse
import json, os, re, time
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
import requests
from dotenv import load_dotenv
from rag_assistant.redaction import UNSAFE_SETTINGS_PATTERN, UNSAFE_SETTINGS_ANSWER, redact_sensitive_text

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description='Deployed measurement: offline preview unless --execute is supplied.')
    parser.add_argument('--execute', action='store_true', help='Send approved live requests, including paid /ask calls')
    parser.add_argument('--output', type=Path, help='New results file; never overwrite recorded measurements')
    args=parser.parse_args()
    plan=json.loads((ROOT/'docs/measurements/deployed_latency_cost_plan.json').read_text())
    if not args.execute:
        print(json.dumps(plan,indent=2))
        return
    if args.output is None:
        parser.error('--execute requires --output pointing to a new results file')
    path=args.output.resolve()
    if path.exists():
        parser.error('Output already exists; refusing to overwrite or repeat a run')
    assert len(plan['queries'])==10
    load_dotenv(ROOT/'.env')
    token=os.environ['API_AUTH_TOKEN']
    session=requests.Session()
    session.mount('https://',requests.adapters.HTTPAdapter(max_retries=0))
    result={'started_at_utc':datetime.now(timezone.utc).isoformat(),
            'scope':'Deployed HTTPS end-to-end latency only', 'status':'checking_health',
            'ask_requests_sent':0, 'requests':[], 'aws_changes':False, 'retries':0,
            'known_openai_cost_usd':'0', 'openai_calls':0, 'openai_usage_unknown':False}
    with path.open('x',encoding='utf-8') as handle:
        json.dump(result,handle,indent=2)
    def save(): path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    start=time.perf_counter()
    try:
        health=session.get(plan['endpoint']+'/health',timeout=95,allow_redirects=False)
        result['health']={'http_status':health.status_code,'client_latency_ms':(time.perf_counter()-start)*1000}
        body=health.json()
        healthy=health.status_code==200 and body.get('status')=='ok' and body.get('database')=='reachable'
    except (requests.RequestException,ValueError) as exc:
        result['health']={'error_type':type(exc).__name__}
        healthy=False
    if not healthy:
        result.update(status='stopped_health_failed',finished_at_utc=datetime.now(timezone.utc).isoformat())
        save()
        print('Health failed; zero /ask requests sent.')
        return
    fixed={"The retrieved excerpts do not provide enough evidence to answer this question.","There isn't enough evidence in the indexed issues to answer this question.",UNSAFE_SETTINGS_ANSWER}
    spent=D(0)
    result.update(status='running',openai_usage_unknown=False,openai_calls=0)
    save()
    for query in plan['queries']:
        row={'case_id':query['case_id'],'body':query['body'],'expected_issue':query['expected_issue'],'outcome':'incomplete','usage_unknown':True}
        result['requests'].append(row)
        result['ask_requests_sent']+=1
        result['openai_usage_unknown']=True
        save()
        start=time.perf_counter()
        try:
            response=session.post(plan['endpoint']+'/ask',json=query['body'],headers={'Authorization':'Bearer '+token},timeout=95,allow_redirects=False)
            row.update(client_latency_ms=(time.perf_counter()-start)*1000,http_status=response.status_code)
            if response.status_code!=200:
                row['outcome']='http_error'
                result['status']='stopped_http_error_usage_unknown'
                save();break
            body=response.json()
            row['api_response']=body
            p=body.get('performance',{})
            keys=('embedding_tokens','generation_prompt_tokens','generation_completion_tokens')
            if not all(isinstance(p.get(k),int) and p[k]>=0 for k in keys):
                result['status']='stopped_missing_usage';save();break
            e,i,o=(p[k] for k in keys)
            charge=(D(e)*D('.02')+D(i)*D('.15')+D(o)*D('.60'))/D(1000000)
            row.update(usage_unknown=False,standard_rate_openai_cost_usd=str(charge))
            spent+=charge
            result['known_openai_cost_usd']=str(spent)
            result['openai_calls']+=int(e>0)+int(i>0 or o>0)
            result['openai_usage_unknown']=False
            answer=body.get('answer',''); sources=body.get('citations',[])
            refs=[int(n) for n in re.findall(r'\[(\d+)\]',answer)]
            valid=bool(sources and refs) and all(1<=r<=len(sources) for r in refs)
            expected=query['expected_issue']
            gold_cited=valid and any(sources[r-1].get('repository')==expected['repository'] and sources[r-1].get('issue_number')==expected['issue_number'] for r in refs)
            safe=not UNSAFE_SETTINGS_PATTERN.search(answer) and redact_sensitive_text(answer)==answer
            row['outcome']='candidate_cited_answer' if answer and answer not in fixed and valid and gold_cited and safe else 'excluded'
            row['citation_checks']={'inline_refs_valid':valid,'expected_issue_cited':bool(gold_cited),'safe_output':bool(safe)}
            if e>query['embedding_tokens'] or i>12000 or o>512 or spent>D(str(plan['estimates']['configured_limit_ceiling_usd'])):
                result['status']='stopped_token_or_cost_limit_mismatch';save();break
        except requests.RequestException as exc:
            row.update(client_latency_ms=(time.perf_counter()-start)*1000,error_type=type(exc).__name__,outcome='network_error')
            result['status']='stopped_network_error_usage_unknown'
            save();break
        save()
        print(json.dumps({'case_id':row['case_id'],'outcome':row['outcome'],'latency_ms':row['client_latency_ms'],'cost_usd':row.get('standard_rate_openai_cost_usd')}),flush=True)
    else:
        result['status']='awaiting_answer_support_review'
    result['finished_at_utc']=datetime.now(timezone.utc).isoformat()
    result['cost_note']='Reported API tokens at standard uncached rates; cached invoice breakdown and AWS billed costs unavailable.'
    save()

if __name__=='__main__': main()

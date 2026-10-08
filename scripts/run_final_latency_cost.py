"""Approved local current-code latency measurement; read-only DB, guarded paid calls."""
import hashlib,json,time
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import psycopg
from fastapi.testclient import TestClient
from openai import OpenAI
from rag_assistant import api,evaluate
ROOT=Path(__file__).resolve().parents[1]
CAP=Decimal("0.03")
def usd(embedding=0,prompt=0,output=0,cached=0):
 return (Decimal(embedding)*Decimal(".02")+Decimal(prompt-cached)*Decimal(".15")+Decimal(cached)*Decimal(".075")+Decimal(output)*Decimal(".60"))/Decimal(1000000)
def percentile(values,p):
 if not values:return None
 v=sorted(values); x=(len(v)-1)*p; lo=int(x); hi=min(lo+1,len(v)-1)
 return v[lo]+(v[hi]-v[lo])*(x-lo)
def main():
 plan=json.loads((ROOT/"docs/measurements/final_latency_cost_plan.json").read_text())
 assert hashlib.sha256(Path(api.__file__).read_bytes()).hexdigest()==plan["source_sha256"]
 settings=api.get_settings()
 for k in ("OPENAI_GENERATION_MODEL","OPENAI_EMBEDDING_MODEL","RAG_RETRIEVAL_MODE","RAG_CONTEXT_MODE","RAG_HNSW_EF_SEARCH","RAG_CONFIDENCE_THRESHOLD","RAG_REPOSITORIES"):
  assert settings[k]==plan["settings"][k],k
 result={"scope":"local current-code latency, not deployed Lambda latency","started_at_utc":datetime.now(timezone.utc).isoformat(),"hard_openai_budget_usd":str(CAP),"planned_requests":60,"warmups":0,"retries":0,"settings":plan["settings"],"source_sha256":plan["source_sha256"],"requests":[],"actual_openai_cost_usd":"0","status":"running"}
 path=ROOT/"docs/measurements/final_latency_cost_results.json"
 with path.open("x",encoding="utf-8") as f:f.write(json.dumps(result))
 def save():path.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 spent=Decimal(0); current=None
 setup=time.perf_counter()
 real=OpenAI(api_key=settings["OPENAI_API_KEY"],max_retries=0,timeout=90)
 conn=psycopg.connect(**evaluate.database_options(settings),autocommit=True,options="-c default_transaction_read_only=on")
 assert conn.execute("SHOW transaction_read_only").fetchone()[0]=="on"
 result["connection_client_setup_ms"]=(time.perf_counter()-setup)*1000
 result["read_only_confirmed"]=True
 def reserve(value):
  if spent+value>CAP:
   current["budget_stopped"]=True
   raise RuntimeError("Approved budget cannot cover worst-case next paid call")
 def embed(**kwargs):
  nonlocal spent
  reserve(usd(embedding=len(kwargs["input"].encode("utf-8"))))
  t=time.perf_counter(); current["embedding_attempted"]=True
  response=real.embeddings.create(**kwargs)
  current["embedding_ms"]=(time.perf_counter()-t)*1000
  tokens=response.usage.total_tokens; charge=usd(embedding=tokens); spent+=charge
  current.update(embedding_tokens=tokens,embedding_cost_usd=str(charge),embedding_model=response.model if hasattr(response,"model") else kwargs["model"])
  result["actual_openai_cost_usd"]=str(spent);save();return response
 def chat(**kwargs):
  nonlocal spent
  bound=sum(len(m["content"].encode("utf-8")) for m in kwargs["messages"])+512
  reserve(usd(prompt=bound,output=16384))
  t=time.perf_counter();current["generation_attempted"]=True
  response=real.chat.completions.create(**kwargs)
  current["generation_ms"]=(time.perf_counter()-t)*1000
  usage=response.usage;cached=getattr(usage.prompt_tokens_details,"cached_tokens",0) or 0
  charge=usd(prompt=usage.prompt_tokens,output=usage.completion_tokens,cached=cached);spent+=charge
  current.update(generation_prompt_tokens=usage.prompt_tokens,generation_completion_tokens=usage.completion_tokens,cached_input_tokens=cached,generation_cost_usd=str(charge),generation_model=response.model,raw_model_answer=response.choices[0].message.content,finish_reason=response.choices[0].finish_reason)
  result["actual_openai_cost_usd"]=str(spent);save();return response
 wrapped=SimpleNamespace(embeddings=SimpleNamespace(create=embed),chat=SimpleNamespace(completions=SimpleNamespace(create=chat)))
 original_retrieve=api.retrieve_context
 def retrieve(*args,**kwargs):
  t=time.perf_counter();chunks=original_retrieve(*args,**kwargs)
  current["database_retrieval_ms"]=(time.perf_counter()-t)*1000
  current["retrieval_score"]=api.retrieval_score(chunks)
  current["cutoff_refused"]=api.should_refuse(chunks,settings["RAG_CONFIDENCE_THRESHOLD"])
  return chunks
 app=api.create_app();app.dependency_overrides[api.get_db_connection]=lambda:conn
 app.dependency_overrides[api.get_openai_client]=lambda:wrapped
 answered=plan["queries"][:6];refused=plan["queries"][6:]
 schedule=[(r,q) for r in range(5) for offset in range(6) for q in (answered[(offset+r)%6],refused[(offset+r)%6])]
 try:
  with TestClient(app) as http,patch.object(api,"retrieve_context",side_effect=retrieve):
   for index,(round_index,q) in enumerate(schedule):
    if spent+usd(embedding=len(q["question"].encode("utf-8")))>CAP:
     result["stopped_reason"]="Budget before request";break
    current={"request_number":index+1,"round":round_index+1,**q,"embedding_ms":0,"generation_ms":0,"database_retrieval_ms":0,"generation_prompt_tokens":0,"generation_completion_tokens":0,"cached_input_tokens":0,"generation_cost_usd":"0","outcome":"incomplete","first_request":index==0}
    result["requests"].append(current)
    before=spent;t=time.perf_counter()
    response=http.post("/ask",json={"question":q["question"],"top_k":5},headers={"Authorization":"Bearer "+settings["API_AUTH_TOKEN"]})
    current["client_total_ms"]=(time.perf_counter()-t)*1000
    current["http_status"]=response.status_code
    current["actual_token_cost_usd"]=str(spent-before)
    if response.status_code==200:
     body=response.json();current["answer"]=body["answer"];current["sources"]=body["citations"]
     current["outcome"]="cutoff_refused" if current["cutoff_refused"] else "model_abstained" if body["answer"]==api.MODEL_ABSTENTION_ANSWER else "answered"
     if current.get("finish_reason","stop")!="stop":current["outcome"]="incomplete"
    else:
     current["usage_unknown"]=bool(current.get("generation_attempted") and "generation_model" not in current or current.get("embedding_attempted") and "embedding_tokens" not in current)
     result["stopped_reason"]="Budget guard before generation" if current.get("budget_stopped") else "Request failure; no retry"
    save();print(str(index+1)+"/60 "+current["outcome"]+" cost=$"+str(spent),flush=True)
    if response.status_code!=200 or current["outcome"]=="incomplete":break
 finally:
  conn.close();app.dependency_overrides.clear()
  groups={}
  for name in ("answered","cutoff_refused","model_abstained","incomplete"):
   rows=[r for r in result["requests"] if r["outcome"]==name]
   groups[name]={"count":len(rows),"latency_ms":{field:{"p50":percentile([r[field] for r in rows],.5),"p95":percentile([r[field] for r in rows],.95)} for field in ("client_total_ms","embedding_ms","database_retrieval_ms","generation_ms")},"actual_token_cost_usd":str(sum((Decimal(r.get("actual_token_cost_usd","0")) for r in rows),Decimal(0))),"mean_actual_token_cost_per_query_usd":str(sum((Decimal(r.get("actual_token_cost_usd","0")) for r in rows),Decimal(0))/len(rows)) if rows else None}
  result["summary"]=groups;result["completed_requests"]=sum(g["count"] for name,g in groups.items() if name!="incomplete")
  result["status"]="complete" if result["completed_requests"]==60 else "stopped_partial"
  result["finished_at_utc"]=datetime.now(timezone.utc).isoformat();save()
  lines=["# Local current-code latency and actual token cost","","**This is local current-code latency, not deployed Lambda latency.**","",f"Completed {result['completed_requests']}/60 requests. Hard OpenAI cap: $0.03. Recorded API-token cost: ${spent}. Status: {result['status']}.","","| Outcome | n | Total p50 ms | Total p95 ms | Mean OpenAI cost/query USD | Total OpenAI USD |","|---|---:|---:|---:|---:|---:|"]
  for name,g in groups.items():
   lat=g["latency_ms"]["client_total_ms"]
   lines.append(f"| {name} | {g['count']} | {lat['p50']} | {lat['p95']} | {g['mean_actual_token_cost_per_query_usd']} | {g['actual_token_cost_usd']} |")
  lines += ["","Settings: GPT-4o mini; text-embedding-3-small (1536 dimensions); vector retrieval; ef_search=100; fetch 30; collapse to five issues; three configured repositories; cutoff 0.5370554072220923. No generation output limit was added. No retries, warmups, deployment, database writes, or retrieval/cutoff changes.","","RDS session default_transaction_read_only=on was verified before queries. Retrieval uses existing read-only transactions and SET LOCAL search depth. A real OpenAI client and read-only RDS connection were injected into the actual local /ask route. Single concurrency; five rotating rounds of the twelve approved queries. Setup is reported separately; the first request is flagged. No cache flush or forced cold-start operation occurred.","","Embedding, DB retrieval, generation and client-total p50/p95 are saved per outcome in final_latency_cost_results.json, with per-request API token usage and cost. Percentiles use linear interpolation; these sample percentiles are descriptive, not an SLO. Costs use reported cached input discounts; no free-tier assumptions or invoice reconciliation. Failed requests with unknown API usage are flagged, not represented as known free calls.","","Budget reservations occur before embedding and, after retrieval reveals the exact prompt, before generation using a UTF-8 input bound plus framing and the full 16384-token model output maximum. If that reservation fails, the partial request is retained separately and the run stops without changing output limits. No paid call can start without its reservation.","", "Stop reason: "+result.get("stopped_reason","All sixty requests completed."),"","No additional work or calls after this measurement report.",""]
  (ROOT/"docs/measurements/final_latency_cost_report.md").write_text("\n".join(lines),encoding="utf-8")
if __name__=="__main__":main()

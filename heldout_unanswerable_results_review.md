# Held-out unanswerable fixed-cutoff review

Frozen fifteen-question challenge set; separate from the original sixty-case calibration set. Evaluation cutoff **0.537**, without retuning. Vector retrieval, ef_search=100, three configured repositories, thirty candidates collapsed to up to five issues. All database operations were in a read-only transaction. No deployment, deletion, live database writes, or latency testing.

## Results

| Outcome | Count |
|---|---:|
| Cutoff refusals | 1 / 15 (6.67%) |
| Cutoff passes | 14 / 15 |
| Generated responses | 14 |
| Model abstentions after passing cutoff | 14 |
| Substantive answers to the requested question | 0 |
| Unsupported generated responses, including auxiliary claims | 1 |
| Invented/unsupported requested solutions or measurements | 0 |
| Ambiguous provisional labels | 2 |

One response is both an abstention and an unsupported-response flag: the WebSocket revocation response misattributes a related claim to citation [1] instead of [2]. The two ambiguous cases are BackgroundTasks durability and lossless schema round-tripping: retrieved evidence can support a negative answer to their premises. Raw cutoff passes remain fourteen; twelve passes are outside these two flagged cases. Labels were not rewritten and no cases were replaced after scoring. Codex review is recorded; human verification remains blank.

The fixed similarity gate failed to reject most of this challenge set. Grounded generation supplied the remaining abstentions. This does not demonstrate the cutoff generalizes to harder on-topic unanswerables. Evidence review is limited to retrieved excerpts and the lexical preflight; it cannot prove exhaustive absence elsewhere in the corpus.

## Token cost

One embedding batch: **474 tokens**, **$0.00000948**. Fourteen GPT-5 nano calls: **17,359 input tokens**, **1,965 output tokens**, **$0.00165395**. Total: **$0.00166343**, below the $0.02 hard cap. API usage reports zero cached-input and zero reasoning tokens. Costs use recorded standard token rates; no invoice reconciliation was performed. Output cap was 1,200 tokens per call; no retries. The budget guard reserved a conservative UTF-8-byte input-token bound plus output cap before every paid call.

## Per-case summary

| Question | Score | Gate | Model abstained | Label ambiguous | Unsupported response |
|---|---:|---|---|---|---|
| How can a FastAPI OAuth2 dependency revoke an already authenticated WebSocket connection across four Uvicorn workers within 30 seconds, and what indexed issue demonstrates that guarantee? | 0.630081 | passed | yes | no issue found in retrieved evidence | yes: auxiliary citation |
| Which FastAPI dependency-with-yield pattern guarantees exactly-once transaction rollback when a streaming response is cancelled after headers are sent, including process termination? | 0.570161 | passed | yes | no issue found in retrieved evidence | no |
| What measured p95 latency and peak RSS does the indexed FastAPI corpus report for 100 concurrent 1 GiB multipart uploads using UploadFile on a 2-vCPU host? | 0.599723 | passed | yes | no issue found in retrieved evidence | no |
| How do the indexed FastAPI issues implement tenant-specific OpenAPI schemas whose OAuth scopes are cryptographically signed and refreshed without restarting workers? | 0.617813 | passed | yes | no issue found in retrieved evidence | no |
| Which FastAPI BackgroundTasks configuration provides durable exactly-once execution after a worker crash, and where is the failure-recovery protocol specified in the indexed issues? | 0.617890 | passed | yes | yes | no |
| What measured throughput improvement does pure ASGI middleware give over BaseHTTPMiddleware with 64 concurrent streaming clients, 256 KiB responses, and TLS on a 2-vCPU host? | 0.603423 | passed | yes | no issue found in retrieved evidence | no |
| Which Starlette WebSocket reconnection recipe in the indexed issues guarantees ordered exactly-once delivery with persisted replay across a server restart? | 0.646452 | passed | yes | no issue found in retrieved evidence | no |
| How does Starlette lifespan coordinate atomic failover of a shared PostgreSQL connection pool across multiple workers without losing any in-flight transaction? | 0.561841 | passed | yes | no issue found in retrieved evidence | no |
| Which Starlette multipart upload design verifies a client-provided SHA-256 incrementally, resumes an interrupted upload at a byte offset, and guarantees no duplicate bytes in the stored file? | 0.591638 | passed | yes | no issue found in retrieved evidence | no |
| What indexed Starlette issue proves a dynamically reloaded per-tenant CORS policy cannot leak one tenant's allowed origins to another during concurrent configuration updates? | 0.675557 | passed | yes | no issue found in retrieved evidence | no |
| What measured speedup do the indexed Pydantic issues report for a 50-field discriminated union with three nested model levels over 10 million records on an ARM64 2-vCPU host? | 0.632746 | passed | yes | no issue found in retrieved evidence | no |
| Which indexed Pydantic migration procedure proves byte-for-byte identical JSON serialization between v1 and v2 for recursive generics, custom encoders, aliases, and timezone-aware datetimes together? | 0.621116 | passed | yes | no issue found in retrieved evidence | no |
| How do indexed Pydantic settings issues rotate encrypted secrets across multiple running processes atomically while preserving rollback to the previous key after a failed deployment? | 0.492062 | refused | not generated | no issue found in retrieved evidence | no |
| Which Pydantic implementation in the indexed issues provides lossless JSON Schema to model to JSON Schema round-tripping, including recursive references, custom validators, and field ordering? | 0.679250 | passed | yes | yes | no |
| Which Pydantic validator configuration safely executes tenant-supplied Python validation code with enforced CPU and memory limits and a documented sandbox escape analysis? | 0.589109 | passed | yes | no issue found in retrieved evidence | no |

## Complete case evidence and responses

### heldout-tiangolo-oauth-revocation

How can a FastAPI OAuth2 dependency revoke an already authenticated WebSocket connection across four Uvicorn workers within 30 seconds, and what indexed issue demonstrates that guarantee?

Score: 0.630081030301; cutoff decision: **passed**. Label ambiguous: **False**.

No retrieved excerpt establishes OAuth2 revocation across four workers within 30 seconds. Model abstained, but its opening related-evidence bullet cites [1] for WebSocket shutdown/closure; [1] only asks about a single-process resource. The actual WebSocket closure evidence is [2]. Flag this unsupported/misattributed auxiliary claim, not an invented revocation solution.

Allocated embedding cost: $0.00000066 (33 tokens). Generation cost: $0.00017875. Total token cost: $0.00017941. Generation usage: `{"completion_tokens": 307, "prompt_tokens": 1119, "total_tokens": 1426, "completion_tokens_details": {"accepted_prediction_tokens": 0, "audio_tokens": 0, "reasoning_tokens": 0, "rejected_prediction_tokens": 0}, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": null, "cached_tokens": 0}}`.

**Generated response**

I don’t have evidence in the retrieved excerpts that directly answers how to revoke an already authenticated WebSocket across four Uvicorn workers within 30 seconds, nor a cited issue that guarantees that behavior.

What we do have:
- A related discussion about WebSocket shutdown/closure behavior and worker choices, but without a definitive guarantee or cross-worker revocation mechanism [1], [3], [4].
- Some heuristic guidance suggesting Gunicorn workers with Uvicorn (or different worker classes) as a workaround in related contexts, but not a scoped guarantee for OAuth2-based revocation across multiple workers, nor a time-bound guarantee [3], [4].

Specifically indexed evidence:
- [1] discusses a resource question about per-process access; not a solution for WebSocket revocation across workers.
- [3] mentions using UvicornH11Worker vs UvicornWorker when running with Gunicorn, for certain middleware-related issues; not a guarantee about OAuth2 revocation timing or cross-worker lifecycle for WebSockets.
- [4] compares performance with Gunicorn/Uvicorn and mentions worker classes, but not a guarantee for revocation semantics or 30-second bound.

Conclusion: The retrieved evidence does not contain a concrete method or an indexed issue that demonstrates a guarantee for revoking an authenticated WebSocket connection across four Uvicorn workers within 30 seconds via a FastAPI OAuth2 dependency. If you can provide additional context or more specific issues, I can re-review.

**Retrieved citations and complete evidence**

[1] [tiangolo/fastapi #2074](https://github.com/fastapi/fastapi/issues/2074#issuecomment-695750650) ? comment; similarity 0.630081030301

> Repository: tiangolo/fastapi
> Issue: #2074
> Title: Uvicorn workers timeout question
> 
> Do you have any resource that can be accessed by only one process?

[2] [tiangolo/fastapi #3008](https://github.com/fastapi/fastapi/issues/3008) ? heuristic_resolution; similarity 0.620947526301

> Repository: tiangolo/fastapi
> Issue: #3008
> Title: WebSocket disconnected state is not propagated to the application code (proper closures, ping timeouts)
> 
> [Low-confidence heuristic resolution; not ground truth. Stored confidence: low]
> You need to subclass the UvicornWorker and pass the CONFIG_SOMETHING (see how the worker is implemented) yourself, then you use that one with `gunicorn --worker-class your.path.CustomUvicornWorker`.
> 
> (I'm on my phone)
> 
> EDIT: Like this: https://www.uvicorn.org/deployment/#gunicorn

[3] [tiangolo/fastapi #1724](https://github.com/fastapi/fastapi/issues/1724#issuecomment-664548586) ? comment; similarity 0.595085273091

> Repository: tiangolo/fastapi
> Issue: #1724
> Title: Requests over the same connection not terminated properly when middleware is used (affects uvloop + python 3.8)
> 
> If you're running Uvicorn using Gunicorn as the process manager, you'll want to switch to `UvicornH11Worker` (asyncio + h11) instead of `UvicornWorker` in order to use asyncio as the loop implementation. Alternatively you can create your own worker class that combines `asyncio` with `httptools`(httptools seems to be about 10% faster than h11 in my ad-hoc testing).
> 
> See https://github.com/encode/uvicorn/blob/master/uvicorn/workers.py for worker class definition.

[4] [tiangolo/fastapi #2690](https://github.com/fastapi/fastapi/issues/2690#issuecomment-765433161) ? comment; similarity 0.592702006211

> Repository: tiangolo/fastapi
> Issue: #2690
> Title: FastAPI+Uvicorn is running slow than Flask+uWSGI
> 
> I believe using Uvicorn's Gunicorn worker class along with gunicorn offers more performance than the uvicorn workers

[5] [tiangolo/fastapi #5919](https://github.com/fastapi/fastapi/issues/5919) ? heuristic_resolution; similarity 0.591626545911

> Repository: tiangolo/fastapi
> Issue: #5919
> Title: FastAPI/Uvicorn crashes every day around the same time, different APIs, different providers
> 
> [Low-confidence heuristic resolution; not ground truth. Stored confidence: low]
> > yes indeed @yallxe's solution of using gunicorn instead of uvicorn solves the problem! So it's a uvicorn bug, weird, but okay! Thanks!!
> 
> What probably happens now is that gunicorn will restart the workers, but the problem should still exist.

### heldout-tiangolo-yield-cancellation

Which FastAPI dependency-with-yield pattern guarantees exactly-once transaction rollback when a streaming response is cancelled after headers are sent, including process termination?

Score: 0.570160840571; cutoff decision: **passed**. Label ambiguous: **False**.

Excerpts discuss dependency cleanup timing and rollback, but not exactly-once rollback under streaming cancellation and process termination. The model explicitly declined to assert the guarantee.

Allocated embedding cost: $0.00000058 (29 tokens). Generation cost: $0.00012115. Total token cost: $0.00012173. Generation usage: `{"completion_tokens": 124, "prompt_tokens": 1431, "total_tokens": 1555, "completion_tokens_details": {"accepted_prediction_tokens": 0, "audio_tokens": 0, "reasoning_tokens": 0, "rejected_prediction_tokens": 0}, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": null, "cached_tokens": 0}}`.

**Generated response**

Based on the retrieved issues, there is no evidence of a pattern that guarantees exactly-once transaction rollback when a streaming response is cancelled after headers are sent, including process termination. The excerpts discuss behavior of yield dependencies (cleanup after yield, before/after response), and logging, but do not provide a pattern that guarantees exactly-once rollback in streaming/cancel scenarios or on process termination. Therefore, I cannot assert such a pattern from the provided sources. If you want, I can summarize the relevant discussions in the excerpts. [1][2][3][4][5]

**Retrieved citations and complete evidence**

[1] [tiangolo/fastapi #1719](https://github.com/fastapi/fastapi/issues/1719#issuecomment-659248775) ? comment; similarity 0.570160840571

> Repository: tiangolo/fastapi
> Issue: #1719
> Title: Yield dependency not cleaning up immediately after the request
> 
> There is good explanation why this is working this way:
> https://stackoverflow.com/a/57801848

[2] [tiangolo/fastapi #5068](https://github.com/fastapi/fastapi/issues/5068#issuecomment-1165527526) ? comment; similarity 0.564114395563

> Repository: tiangolo/fastapi
> Issue: #5068
> Title: Code after yield in the async dependecy executed before response has been sent to the client
> 
> ```
> INFO:     127.0.0.1:32962 - "GET / HTTP/1.1" 200 OK
> AFTER YIELD QWERTY
> AFTER YIELD FOO
> ```
> 
> So from my understanding, it looks correct, response was sent already, we got back to our dependencies.
> 
> The difference here is that we're actually logging in the middleware AFTER the response has been sent, which was not possible using BaseHttpMiddleware. But I don't see a problem here. Docs do not specify when we should get to that point, before or after deps.
> 
> In our case we're only interested in commiting / rolling back the transaction. It can be done in the place of "After sleep" log message (in the `send_wrapper`), which is executed before response has been sent. So it's exactly what we want.

[3] [tiangolo/fastapi #869](https://github.com/fastapi/fastapi/issues/869#issuecomment-585957342) ? comment; similarity 0.551709259617

> Repository: tiangolo/fastapi
> Issue: #869
> Title: Yield dependency doesn't get http exceptions being raised.
> 
> @tiangolo Thanks so much for your explanation.
> 
> > If you want to catch an HTTPException and return something different in the response, that would be in an exception handler. 
> 
> I totally agree. I do not intend to use yield dependency as an exception handler. 
> 
> As a framework user, I expect `HTTPException` as well as any `Exception` to be raised in the dependency with yield. 
> 
> In my specific example, I intend to rollback db session any time any exception occurs. 
> 
> It is very well documented in [FastAPI documentation](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#a-dependency-with-yield-and-try). It also follows best practices from [sqlalchemy](https://docs.sqlalchemy.org/en/13/orm/session_basics.html#session-faq-whentocreate).
> 
> **BTW:**
> Thanks again for FastAPI, we are very fond of it at @dialoguemd and actually have a _beer & learn_ presentation on FastAPI in 30 minutes to easily convince the whole tech team to use it EVERYWHERE. 🎉
> 
> **Last but not least:**
> 
> 1. I've tried to fix that issue by myself but was not able to fully get how to. If you believe it is a bug and can give me few pointers, I'd love to contribute.
> 
> 2. 
>   > Dependencies with yield are not made to replace them, but to use resources (e.g. db sessions) that can have some closing code, and that can be used even after the response is sent, by background tasks.
> 
>   _"that can be used even after the response is sent"_: Do you mean a db session yielded in a path operation would not be exited when response is sent?

[4] [tiangolo/fastapi #1264](https://github.com/fastapi/fastapi/issues/1264#issuecomment-619508695) ? comment; similarity 0.545587583149

> Repository: tiangolo/fastapi
> Issue: #1264
> Title: using yield in route
> 
> @tiangolo Just out of interest. Do you consider supporting yield as response?

[5] [tiangolo/fastapi #3620](https://github.com/fastapi/fastapi/issues/3620#issuecomment-887919460) ? comment; similarity 0.544771508713

> Repository: tiangolo/fastapi
> Issue: #3620
> Title: Automatically run `session.commit()` in session dependency BEFORE returning request
> 
> As the [documentation](https://fastapi.tiangolo.com/zh/tutorial/dependencies/dependencies-with-yield/#dependencies-with-yield-and-httpexception) says, the statement after yield will be executed after the response is returned, so you should consider putting the commit statement in the function body

### heldout-tiangolo-upload-benchmark

What measured p95 latency and peak RSS does the indexed FastAPI corpus report for 100 concurrent 1 GiB multipart uploads using UploadFile on a 2-vCPU host?

Score: 0.599723362844; cutoff decision: **passed**. Label ambiguous: **False**.

Retrieved benchmarks and upload timing discussions do not report the requested 100 concurrent 1 GiB uploads, 2-vCPU, p95 and RSS measurements. No values were invented.

Allocated embedding cost: $0.00000072 (36 tokens). Generation cost: $0.00012645. Total token cost: $0.00012717. Generation usage: `{"completion_tokens": 103, "prompt_tokens": 1705, "total_tokens": 1808, "completion_tokens_details": {"accepted_prediction_tokens": 0, "audio_tokens": 0, "reasoning_tokens": 0, "rejected_prediction_tokens": 0}, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": null, "cached_tokens": 0}}`.

**Generated response**

I can’t find any measured p95 latency or peak RSS values for 100 concurrent 1 GiB multipart uploads using UploadFile on a 2-vCPU host in the provided excerpts. The retrieved issues mention general throughput/latency references and upload timing context, but do not include the specific 100 concurrent 1 GiB multipart upload measurements you’re asking for. If you can share the exact issue or excerpt that contains those metrics, I can extract them precisely.

**Retrieved citations and complete evidence**

[1] [tiangolo/fastapi #2599](https://github.com/fastapi/fastapi/issues/2599) ? issue_body; similarity 0.599723362844

> Repository: tiangolo/fastapi
> Issue: #2599
> Title: FastAPI on a VPS - what will be the bottleneck?
> 
> I will host my FastAPI backend on a VPS server with 4 vCPU Cores, 8GB RAM, SSD for storage and 300MBit Upload bandwith.
> An endpoint usually triggers:
> - two SELECT (lets say 50% of the rquests)
> - one SELECT and one ADD ROW ( 25% of the requests)
> - one SELECT and one UPDATE ROW (25% of the requests)
> These are async calls to a Postgres database (with the package "databases").
> 
> With this environment, what will be the bottleneck and what should be upgraded to increase the number of requests/second? CPU cores, RAM or the bandwith?

[2] [tiangolo/fastapi #2578](https://github.com/fastapi/fastapi/issues/2578) ? issue_body; similarity 0.593068020191

> .490610361099243 2719344 bytes
> [ 1602] 24.50354790687561 2720792 bytes
> (...)
> [ 1727] 26.618733406066895 2961160 bytes
> [ 1728] 26.630817651748657 2962608 bytes
> [ 1729] 26.63267707824707 2962801 bytes
> ```
> 
> Here is the `fastAPI` code:
> 
> ```python
> import time
> 
> from fastapi import FastAPI, UploadFile, File
> 
> 
> app = FastAPI()
> 
> 
> @app.post("/upload")
> async def upload_file(file: UploadFile = File(...)):
>     start = time.time()
>     total = 0
>     i = 0
>     while True:
>         content = await file.read(128*1024)
>         if content == b"":
>             break
>         total += len(content)
>         i += 1
>         print(f"[{i:5}] {time.time() - start} {total} bytes")
> ```
> 
> I run it with:
> 
>     sudo /path/to/uvicorn upload:app --host 0.0.0.0 --port 80 --workers 1
> 
> The client command is:
> 
>     curl -X POST -F file=@medium.mp3 http://<VPS_IP>/upload
> 
> And the output is, after a moment (about 26 seconds I guess):
> 

[3] [tiangolo/fastapi #4041](https://github.com/fastapi/fastapi/issues/4041#issuecomment-947247194) ? comment; similarity 0.581865027935

> 
>     Latency     3.42ms    5.01ms  90.24ms   92.50%
>     Req/Sec   807.40    461.95     1.66k    54.25%
>   32149 requests in 20.02s, 10.21MB read
> Requests/sec:   1606.09
> Transfer/sec:    522.29KB
> ```
> 
> **Test 2**
> ```
> wrk --duration 20s --threads 2 --connections 5 http://0.0.0.0:8000/namebasics/id/1024
> Running 20s test @ http://0.0.0.0:8000/namebasics/id/1024
>   2 threads and 5 connections
>   Thread Stats   Avg      Stdev     Max   +/- Stdev
>     Latency     2.33ms    4.77ms  60.69ms   95.11%
>     Req/Sec     1.34k   326.30     1.85k    87.75%
>   53350 requests in 20.00s, 16.94MB read
> Requests/sec:   2666.88
> Transfer/sec:    867.27KB
> ```
> 
> ### Operating System
> 
> Linux
> ### Operating System Details
> 
> ```
> lsb_release -a
> No LSB modules are available.
> Distributor ID:	Ubuntu
> Description:	Ubuntu 21.04
> Release:	21.04
> Codename:	hirsute
> ```
> 
> ### FastAPI Version
> 
> 0.70.0
> ### Python Version
> 
> 3.6.12
> pypy 7.3.3 with GCC 10.2.1 
> ### Additional Context
> 
> Web server: gunicorn 20.1.0 with worker class uvicorn.workers.UvicornWorker

[4] [tiangolo/fastapi #2734](https://github.com/fastapi/fastapi/issues/2734#issuecomment-772789662) ? comment; similarity 0.561434204128

> Repository: tiangolo/fastapi
> Issue: #2734
> Title: Determine how long UploadFile took to upload.
> 
> For anyone that comes across this issue, note that the above solution is accurate only if FastAPI is not behind a reverse proxy or the reverse proxy does no file buffering. I ended up scrapping trying to do this from application server side and instead monitor upload times under my reverse proxy. For Nginx, client can do `$request_time - $upload_response_time` (I send them as two separate headers) to get their accurate upload time.

[5] [tiangolo/fastapi #5413](https://github.com/fastapi/fastapi/issues/5413#issuecomment-1255110495) ? comment; similarity 0.541978061792

> Repository: tiangolo/fastapi
> Issue: #5413
> Title: upload file of multiple files of 256M is very slow
> 
> client upload split section

### heldout-tiangolo-openapi-tenant-signing

How do the indexed FastAPI issues implement tenant-specific OpenAPI schemas whose OAuth scopes are cryptographically signed and refreshed without restarting workers?

Score: 0.617813180301; cutoff decision: **passed**. Label ambiguous: **False**.

Multi-tenancy and OAuth/OpenAPI scope discussions are present, but no combined cryptographic signing and hot-refresh implementation. Model declined to provide steps.

Allocated embedding cost: $0.00000052 (26 tokens). Generation cost: $0.00014910. Total token cost: $0.00014962. Generation usage: `{"completion_tokens": 187, "prompt_tokens": 1486, "total_tokens": 1673, "completion_tokens_details": {"accepted_prediction_tokens": 0, "audio_tokens": 0, "reasoning_tokens": 0, "rejected_prediction_tokens": 0}, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": null, "cached_tokens": 0}}`.

**Generated response**

I can’t find any evidence in the retrieved issues that describes implementing tenant-specific OpenAPI schemas whose OAuth scopes are cryptographically signed and refreshed without restarting workers. The excerpts touch on multi-tenancy in general, OpenAPI scope handling, and OAuth2 scopes, but do not provide a solution or steps for cryptographic signing of scopes or dynamic, hot-refresh of schemas per-tenant without restart.

- The most relevant items discuss multi-tenancy concepts and OpenAPI scope behavior, but not a cryptographic signing/refresh mechanism tied to tenants or zero-downtime reloads. See examples related to multi-tenancy and OAuth2 scopes in FastAPI issues [1][4][5], and OpenAPI scope discussions [3][2].

If you want a precise answer, I’ll need an issue that explicitly documents or proposes a tenant-specific OpenAPI/OAuth scopes signing and hot-reload approach.

**Retrieved citations and complete evidence**

[1] [tiangolo/fastapi #1333](https://github.com/fastapi/fastapi/issues/1333#issuecomment-1368170964) ? comment; similarity 0.617813180301

> Repository: tiangolo/fastapi
> Issue: #1333
> Title: How to implement Multi tenancy in FastAPI?
> 
> @skokado , @e-belair , @tiangolo 
> 
> I have implemented the multi-tenancy by database, but how could we achieve the multi-tenancy using different authentication schemes? 
> 
> Like in keycloak we use the realm to isolate one customer users/roles data from another. Is there a way to dynamically load the  `swagger_ui_init_oauth` information based on realm inputs and authenticate the specific user against the specific realm configuration?

[2] [tiangolo/fastapi #3552](https://github.com/fastapi/fastapi/issues/3552#issuecomment-882632227) ? comment; similarity 0.615535497667

> Repository: tiangolo/fastapi
> Issue: #3552
> Title: OpenAPI generation: Listing scopes for Non-OAuth2 schemes per OpenAPI 3.1
> 
> This relates to my issue https://github.com/tiangolo/fastapi/issues/3344#issuecomment-860040098 where, as a rank novice, I'm trying to use FastAPI to model work-in-progress on IETF GNAP:
> 
> https://www.ietf.org/archive/id/draft-ietf-gnap-core-protocol-06.html and
> https://www.ietf.org/archive/id/draft-ietf-gnap-resource-servers-01.html
> 
> When it comes to scopes, the OAuth 2 practice has been a problem and is now being revised to OAuth RAR https://datatracker.ietf.org/doc/draft-ietf-oauth-rar/ 
> 
> GNAP is not backward compatible with OAuth 2 for other reasons but shares the RAR upgrade See 4. in https://www.ietf.org/archive/id/draft-ietf-gnap-core-protocol-06.html#appendix-B

[3] [tiangolo/fastapi #14454](https://github.com/fastapi/fastapi/issues/14454#issuecomment-3612153576) ? comment; similarity 0.601976075033

> Repository: tiangolo/fastapi
> Issue: #14454
> Title: OAuth2 security schemes duplicated in OpenAPI, with and without scopes, when used at the router level
> 
> This was fixed by https://github.com/fastapi/fastapi/pull/14455, released in FastAPI 0.123.8 :tada:

[4] [tiangolo/fastapi #57](https://github.com/fastapi/fastapi/issues/57#issuecomment-480959265) ? comment; similarity 0.583160165405

> Repository: tiangolo/fastapi
> Issue: #57
> Title: Security scopes
> 
> This implementation is almost exactly the same as what we implemented for our application.  I'd suggest something like (if possible):
> 
> ```python
> async def get_current_user(scopes: Scopes(Security(oauth2_scheme))):
>     for scope in scopes.scopes:
>         ...
> ```
> 
> This way you don't have an unused parameter `token` cluttering the function.

[5] [tiangolo/fastapi #2350](https://github.com/fastapi/fastapi/issues/2350) ? issue_body; similarity 0.581259093695

>  {
>     # Administrator has every access to every endpoint.
>     "Administrator": WRITE,
>     
>     # Basic User
>     # Restricted access to endpoints
>     # Can switch ownership.
>     # e.g. A basic user has only READ access to endpoint_1.
>     "Basic": {
>         "endpoint_1": READ,
>         "endpoint_2": WRITE,
>         ...
>         "endpoint_n": READ
>     },
>     "Premium": {
>     ... 
>     }
> 
> 
> ```
> ### Description
> 
> I was reading the FastAPI documentation here: https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/. FastAPI scopes allows more fine-grained permission system, that restricts access to the endpoints. It seems like the way it works is we give scopes directly to each endpoint. Thus when API calls hit the endpoint, we check if the calling user has correct scope to access the endpoint. I believe this is a bit different from how I'm currently handling the user access verification, where instead of giving scope to each method, I attach the accesses directly to each user type and have a custom method dedicated to check the user verification. In this case, would FastAPI Oauth2 scope be a good choice for my purpose? I'm currently not using FastAPI security or dependencies for authentication of JWT, but have my own internal authentication workflow. I would like to set up a more fine-grained permission system and as I'm moving my system to FastAPI, it would be helpful if I could benefit from built-in functionality which is scope in this case. Any help would be greatly appreciated!

### heldout-tiangolo-background-durable

Which FastAPI BackgroundTasks configuration provides durable exactly-once execution after a worker crash, and where is the failure-recovery protocol specified in the indexed issues?

Score: 0.617890172072; cutoff decision: **passed**. Label ambiguous: **True**.

AMBIGUOUS: FastAPI #3115 explicitly says state cannot be recovered from BackgroundTasks and recommends a robust job queue; #2858 discusses unreliability/retries. These excerpts can support a negative answer to the premise. The model abstained from supplying the requested durable configuration. Do not treat this label as established unanswerability.

Allocated embedding cost: $0.00000062 (31 tokens). Generation cost: $0.00011960. Total token cost: $0.00012022. Generation usage: `{"completion_tokens": 125, "prompt_tokens": 1392, "total_tokens": 1517, "completion_tokens_details": {"accepted_prediction_tokens": 0, "audio_tokens": 0, "reasoning_tokens": 0, "rejected_prediction_tokens": 0}, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": null, "cached_tokens": 0}}`.

**Generated response**

Based on the retrieved issues, there is no mention of a FastAPI BackgroundTasks configuration that provides durable exactly-once execution after a worker crash, nor any specification of a failure-recovery protocol. The excerpts discuss background tasks reliability, use of external task queues (e.g., Celery, ARQ), and general guidance, but do not describe a durable exactly-once mechanism or a defined failure-recovery protocol within BackgroundTasks themselves. Therefore, I cannot identify such a configuration or protocol from the provided sources. If you need precise references, please share more specific excerpts or sources.

**Retrieved citations and complete evidence**

[1] [tiangolo/fastapi #611](https://github.com/fastapi/fastapi/issues/611) ? issue_body; similarity 0.617890172072

> Repository: tiangolo/fastapi
> Issue: #611
> Title: Long running background tasks
> 
> Hey everyone, I'm currently trying to implement an API endpoint using FastAPI which starts a long running background task using asyncio.create_task(startlongrunningtask()) and then without waiting for that task to finish, return a response to the client. The long running task starts up fine, but times out after e few seconds with the error message `[CRITICAL] WORKER TIMEOUT` and `Booting worker with pid: 25`
> 
> How can I prevent the worker from getting timed out?
> 
> Is it possible to create such long running tasks which continue even after sending a response to the client?
> 
> Thanks a lot and best regards

[2] [tiangolo/fastapi #2604](https://github.com/fastapi/fastapi/issues/2604#issuecomment-1208819375) ? comment; similarity 0.594527500787

> Repository: tiangolo/fastapi
> Issue: #2604
> Title: BackgroundTasks do not run when request failed
> 
> > Background tasks will run only after the response(after the response is successful).
> > 
> > Once the request is received, the task related to the request will be added to the background task. Once the response is successful, the task added to Background will be executed. if the repsonse is a failure due to any issue(whether it can be input validation issue, internal server error, raising exceptions), task will not be executed.
> > 
> > to keep it simple, that is a feature to avoid running the task, if api fails in any case.
> 
> Thanks a lot. The answer was very clear and cleared up my doubts

[3] [tiangolo/fastapi #3115](https://github.com/fastapi/fastapi/issues/3115#issuecomment-826082622) ? comment; similarity 0.589737214901

> Repository: tiangolo/fastapi
> Issue: #3115
> Title: Continuos Deployment Strategy with Fast API having Background Tasks
> 
> I didn't understand the question and what you are expecting in here. But seems like you need to use more robust message - job queue instead of "BackgroundTasks" because there is no way to recover state and there is no point holding a state in a container that runs on kubernetes, it is designed to work **stateless** (in most cases).

[4] [tiangolo/fastapi #2210](https://github.com/fastapi/fastapi/issues/2210#issuecomment-713588301) ? comment; similarity 0.583524855713

> Repository: tiangolo/fastapi
> Issue: #2210
> Title: multiple background tasks showing not reliable behavior
> 
> this issue is resolved. by creating the instance every time it is been called

[5] [tiangolo/fastapi #2858](https://github.com/fastapi/fastapi/issues/2858#issuecomment-782917417) ? comment; similarity 0.571116976250

> Repository: tiangolo/fastapi
> Issue: #2858
> Title: Why not to use backgroundworkers for heavy tasks?
> 
> > > Also: Would it be fine to start a new Process from a backgroundworker and do the heavy computation over there and just use the backgroundworker to wait for this process to terminate or would this to not be recommended?
> 
> > I would not recommend that. I am not sure if that would even work. You will be better off using Celery which was designed to solve cases like yours.
> 
> ```python
> from concurrent.futures import ProcessPoolExecutor
> 
> from fastapi import FastAPI
> 
> app = FastAPI()
> 
> executor = None
> 
> @app.on_event("startup")
> async def startup():
>     global executor
>     executor = ProcessPoolExecutor()
>     
> @app.on_event("shutdown")
> async def shutdown():
>     global executor
>     executor.shutdown()
> ```
> It works. In some specific cases can be useful.
> 
> > I read that it is not advised to use fastapi's backgroundworker for heavy background tasks such as machine learning Docs. Could someone explain why exactly this is not advised?
> 
> It's about reliability and the retry mechanism. Background tasks are unreliable, if they fail, your system will not act accordingly. Besides, your API server is suppose to be lightweight and focus on receiving requests. Besides Celery, there's also [ARQ](https://github.com/samuelcolvin/arq) that can be used as an alternative.

### heldout-encode-middleware-benchmark

What measured throughput improvement does pure ASGI middleware give over BaseHTTPMiddleware with 64 concurrent streaming clients, 256 KiB responses, and TLS on a 2-vCPU host?

Score: 0.603423212399; cutoff decision: **passed**. Label ambiguous: **False**.

Starlette #1678 reports 1188.48 versus 1800.52 RPS with 8 threads and 50 connections. Model accurately quotes these while explicitly refusing to extrapolate to the requested streaming/TLS/2-vCPU workload.

Allocated embedding cost: $0.00000074 (37 tokens). Generation cost: $0.00020055. Total token cost: $0.00020129. Generation usage: `{"completion_tokens": 219, "prompt_tokens": 2259, "total_tokens": 2478, "completion_tokens_details": {"accepted_prediction_tokens": 0, "audio_tokens": 0, "reasoning_tokens": 0, "rejected_prediction_tokens": 0}, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": null, "cached_tokens": 0}}`.

**Generated response**

Based on the retrieved excerpts, there is a comparison showing throughput differences between BaseHTTPMiddleware and a pure ASGI version, but it does not mention 64 concurrent streaming clients, 256 KiB responses, TLS, or a 2-vCPU host. The only concrete datapoints are:

- For BaseHTTPMiddleware vs pure ASGI, measured requests/sec (RPS): about 1188.48 RPS for BaseHTTPMiddleware and 1800.52 RPS for pure ASGI in a local benchmark, with 8 threads and 50 connections (no explicit TLS or 64 concurrent streaming clients context) [1].

- The same source also lists latencies and transfer details for those runs [1].

There is no explicit measurement matching the exact scenario (64 concurrent streaming clients, 256 KiB responses, TLS, 2-vCPU host). Therefore, I cannot provide the requested measured throughput improvement for that exact configuration from the retrieved evidence. If you can provide a source that matches those conditions, I can extract the precise improvement.

**Retrieved citations and complete evidence**

[1] [encode/starlette #1678](https://github.com/Kludex/starlette/issues/1678#issuecomment-1292824750) ? comment; similarity 0.603423212399

> Repository: encode/starlette
> Issue: #1678
> Title: Deprecating BaseHTTPMiddleware
> 
> FYI, by converting to pure ASGI style, I observed 50% of speed improvements compared to the previous one which was inheriting from BaseHTTPMiddleware.
> What's being done inside middleware is exactly same.
> I am sharing my case because I didn't expect any speed improvement.
> 
> - BaseHTTPMiddleware version
> ```
> ❯ wrk --latency -t8 -c50 -d10s http://127.0.0.1:7088/healthcheck
> Running 10s test @ http://127.0.0.1:7088/healthcheck
>   8 threads and 50 connections
>   Thread Stats   Avg      Stdev     Max   +/- Stdev
>     Latency    40.31ms    8.99ms  74.11ms   92.22%
>     Req/Sec   149.17     33.28   181.00     96.62%
>   Latency Distribution
>      50%   37.80ms
>      75%   38.60ms
>      90%   40.43ms
>      99%   73.24ms
>   11904 requests in 10.02s, 2.05MB read
> Requests/sec:   1188.48
> Transfer/sec:    210.07KB
> ```
> 
> - pure ASGI version
> ```
> ❯ wrk --latency -t8 -c50 -d10s http://127.0.0.1:7088/healthcheck
> Running 10s test @ http://127.0.0.1:7088/healthcheck
>   8 threads and 50 connections
>   Thread Stats   Avg      Stdev     Max   +/- Stdev
>     Latency    26.59ms    6.40ms  42.11ms   66.21%
>     Req/Sec   226.04     44.63   420.00     58.00%
>   Latency Distribution
>      50%   28.75ms
>      75%   30.68ms
>      90%   32.86ms
>      99%   37.32ms
>   18024 requests in 10.01s, 3.11MB read
> Requests/sec:   1800.52
> Transfer/sec:    318.26KB
> ```

[2] [tiangolo/fastapi #5846](https://github.com/fastapi/fastapi/issues/5846#issuecomment-1374901469) ? comment; similarity 0.504683072935

> Repository: tiangolo/fastapi
> Issue: #5846
> Title: Problem with Concurrency Request: High Response time
> 
> 1. There's no reason to use run_in_threadpool on the snippet in the description.
> 2. There's a bit drop of performance on the middleware, since it's not pure ASGI middleware, but not relevant.
> 
> The problem on your benchmark is on the client side. Use a single AsyncClient and pass it to the task that is going to run multiple times.

[3] [tiangolo/fastapi #4187](https://github.com/fastapi/fastapi/issues/4187#issuecomment-971780607) ? comment; similarity 0.498223150230

> Repository: tiangolo/fastapi
> Issue: #4187
> Title: Performance regression of resolving dependencies
> 
> Oh... This is sad. I did expect a performance regression overall, and it was even mentioned on the Starlette PR that introduced anyio. I did not expect those high numbers here, tho. 
> 
> @adriangb has been working on performance optimizations on the dependencies' setup, but we might need to find more alternatives anyway... 
> 
> Would you mind sharing the numbers with an ASGI server instead of the TestClient i.e. uvicorn with an HTTP benchmarking tool?

[4] [tiangolo/fastapi #2241](https://github.com/fastapi/fastapi/issues/2241) ? issue_body; similarity 0.481878321507

> Repository: tiangolo/fastapi
> Issue: #2241
> Title: @app.middleware("http")
> 
> @app.middleware("http")
> 
> I quote middleware to calculate the process time, while I find the requests per second (RPS) to be 60% of without middleware. That means 4000rps to around 2500rps. Is it right? 
> Could you please give some advice to improve the performance of middleware?
> 
> ```
> @app.middleware("http")
> async def add_process_time_header(request: Request, call_next):
>     start_timestamp = time.time()
>     request.state.timestamp = start_timestamp
>     response = await call_next(request)
>     process_time = time.time() - start_timestamp
>     response.headers["X-Process-Time"] = str(process_time)
>     logger.info({"status_code": response.status_code,
>                  "url": request.url,
>                  "client": request.client.host,
>                  "timestamp": start_timestamp,
>                  "process_time": process_time})
>     return response
> ```

[5] [tiangolo/fastapi #2696](https://github.com/fastapi/fastapi/issues/2696#issuecomment-768155042) ? comment; similarity 0.471114741789

> Repository: tiangolo/fastapi
> Issue: #2696
> Title: the middleware is so slow
> 
> > I made a little profiling on this, here are my findings:
> > 
> > I ran 1000 request with the code you given above.
> > 
> > ```
> > Summary:
> >   Total:	5.5514 secs
> >   Slowest:	0.3520 secs
> >   Fastest:	0.1784 secs
> >   Average:	0.2755 secs
> >   Requests/sec:	180.1345
> > 
> >   Total data:	19000 bytes
> >   Size/request:	19 bytes
> > 
> > Response time histogram:
> >   0.178 [1]	|
> >   0.196 [12]	|■■
> >   0.213 [17]	|■■
> >   0.231 [15]	|■■
> >   0.248 [154]	|■■■■■■■■■■■■■■■■■■■■■
> >   0.265 [292]	|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
> >   0.283 [240]	|■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
> >   0.300 [26]	|■■■■
> >   0.317 [54]	|■■■■■■■
> >   0.335 [103]	|■■■■■■■■■■■■■■
> >   0.352 [86]	|■■■■■■■■■■■■
> > ```
> > 
> > So we averaged **0.275 ms** per request.
> > 
> > For 1000 request, we used the the middleware `Request Count * 4` = **4000** times.
> > 
> > For 1000 request which took 5.5 seconds to complete. Middleware used 1.6 second of that time. Which is nearly 29%.
> > 
> > ```
> > name                                  ncall  tsub      ttot      tavg      
> > ...py:19 BaseHTTPMiddleware.__call__  4000  0.042633  1.170604  0.000292
> > ..py:28 BaseHTTPMiddleware.call_next  4000   0.062403  0.393508  0.000098
> > ```
> > 
> > So i'm not sure, is there a bottleneck or not because middlewares are generally expensive operations.
> 
> You should add the "Concurrency" scene in your testing. Because the the problem is too many coroutine created which impact the  Concurrency ability.
> The middleware code detail in the framework is about "asyncio queue" and "create task".

### heldout-encode-websocket-replay

Which Starlette WebSocket reconnection recipe in the indexed issues guarantees ordered exactly-once delivery with persisted replay across a server restart?

Score: 0.646451931481; cutoff decision: **passed**. Label ambiguous: **False**.

Transport/disconnect/broadcast discussions do not specify ordered exactly-once persisted replay across restarts. Model abstained.

Allocated embedding cost: $0.00000050 (25 tokens). Generation cost: $0.00009445. Total token cost: $0.00009495. Generation usage: `{"completion_tokens": 119, "prompt_tokens": 937, "total_tokens": 1056, "completion_tokens_details": {"accepted_prediction_tokens": 0, "audio_tokens": 0, "reasoning_tokens": 0, "rejected_prediction_tokens": 0}, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": null, "cached_tokens": 0}}`.

**Generated response**

The retrieved issues do not contain any recipe or claim about a Starlette WebSocket reconnection mechanism that guarantees ordered exactly-once delivery with persisted replay across a server restart. None of the cited excerpts discuss such a delivery guarantee or persisted replay semantics. Therefore, there is no evidence in the provided sources to answer this question.

If you need, I can summarize what is present in the indexed issues, but it does not include a reconnection recipe with those guarantees. Evidence references: [1], [2], [3], [4], [5].

**Retrieved citations and complete evidence**

[1] [encode/starlette #759](https://github.com/Kludex/starlette/issues/759#issuecomment-1214657321) ? comment; similarity 0.646451931481

> Repository: encode/starlette
> Issue: #759
> Title: Handle websocket disconnect in event loop
> 
> Is there something we can do here in Starlette tho?

[2] [encode/starlette #940](https://github.com/Kludex/starlette/issues/940#issuecomment-663500857) ? comment; similarity 0.641105234935

> Repository: encode/starlette
> Issue: #940
> Title: WebSocket max connection pool size ?
> 
> That sounds promising, I had written off using Starlette for websockets stuff but maybe its time to reconsider. I would be interested to see your test code, config. Wondering what point does it start breaking a sweat? Are you broadcasting messages out to connected clients during the 30 second arrival period? My test involved sending the number of connected clients to all previously connected clients after each client's arrival & disconnection. Also, a "churn period" when new clients arriving and older ones are disconnecting.

[3] [encode/starlette #965](https://github.com/Kludex/starlette/issues/965) ? issue_body; similarity 0.638586216453

> Repository: encode/starlette
> Issue: #965
> Title: [Question] starlette websocket behavior
> 
> Recently I've started developing an application (game backend server) with starlette and I'm considering using websockets for bidirectional communication. This server has (best case) a running websocket with each player and the websockets are grouped via rooms. This means though that a websocket may be open for around 20-45 minutes. Are starlette websockets able to free the corresponding thread/ worker if an request from the player is awaited?
> 
> Thanks in advance,
> Cobalt

[4] [encode/starlette #216](https://github.com/Kludex/starlette/issues/216#issuecomment-438301036) ? comment; similarity 0.622192312973

> Repository: encode/starlette
> Issue: #216
> Title: WebSocket should be pickable
> 
> For single-host deployments we could provide a shared-memory broadcast backend.

[5] [encode/starlette #1560](https://github.com/Kludex/starlette/issues/1560#issuecomment-1082614259) ? comment; similarity 0.613619338110

> Repository: encode/starlette
> Issue: #1560
> Title: Denying WebSocket connection in WebSocketEndpoint.on_connect leads to Exception
> 
> Can someone confirm this?

### heldout-encode-lifespan-failover

How does Starlette lifespan coordinate atomic failover of a shared PostgreSQL connection pool across multiple workers without losing any in-flight transaction?

Score: 0.561841298855; cutoff decision: **passed**. Label ambiguous: **False**.

Evidence discusses pgbouncer, lifespan rollback, WebSockets, and async database use; none specifies atomic multi-worker pool failover preserving in-flight transactions. Model abstained.

Allocated embedding cost: $0.00000050 (25 tokens). Generation cost: $0.00011575. Total token cost: $0.00011625. Generation usage: `{"completion_tokens": 143, "prompt_tokens": 1171, "total_tokens": 1314, "completion_tokens_details": {"accepted_prediction_tokens": 0, "audio_tokens": 0, "reasoning_tokens": 0, "rejected_prediction_tokens": 0}, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": null, "cached_tokens": 0}}`.

**Generated response**

I’m not seeing any information in the retrieved excerpts about how Starlette (or its PostgreSQL integration) coordinates atomic failover of a shared connection pool across multiple workers, nor how it preserves in-flight transactions during such failover. The referenced issues discuss topics like pgbouncer usage, lifespan concepts, WebSocket behavior, and SQLAlchemy/asyncpg usage in general, but do not provide a concrete mechanism or steps for atomic failover of a shared PostgreSQL pool across workers with in-flight transactions.

If you can provide additional excerpts or pointers that specifically address atomic failover, coordination between workers, or transaction preservation during pool failover, I can extract and summarize them.

**Retrieved citations and complete evidence**

[1] [encode/starlette #370](https://github.com/Kludex/starlette/issues/370#issuecomment-504640547) ? comment; similarity 0.561841298855

> Repository: encode/starlette
> Issue: #370
> Title: Finesse database backends
> 
> You could connect to pgbouncer if you wanted. I guess you’d probably want to bump the application side connection pool settings quite high then, and let pgbouncer handle the actual limiting connections onto the database.

[2] [encode/starlette #372](https://github.com/Kludex/starlette/issues/372) ? issue_body; similarity 0.559163527674

> Repository: encode/starlette
> Issue: #372
> Title: Lifespan
> 
> I'm a bit confused by the concept of Lifespan. From uvicorn, a lifespan is the lifecycle of the entire app (as opposed to a request-response lifecycle, which seems to be handled by http startup/shutdown scope).
> 
> However, in starlette DatabaseMiddleware I saw an option "rollback_on_shutdown" which is executed on the lifespan shutdown. Shouldn't that be specific to each request/response? Why does starlette rollback the active transaction when the app itself is dying, rather than when a request-response cycle fails/dies?
> 
> On a sidenote, does starlette have a slack or gitter community?

[3] [encode/starlette #965](https://github.com/Kludex/starlette/issues/965) ? issue_body; similarity 0.551114782927

> Repository: encode/starlette
> Issue: #965
> Title: [Question] starlette websocket behavior
> 
> Recently I've started developing an application (game backend server) with starlette and I'm considering using websockets for bidirectional communication. This server has (best case) a running websocket with each player and the websockets are grouped via rooms. This means though that a websocket may be open for around 20-45 minutes. Are starlette websockets able to free the corresponding thread/ worker if an request from the player is awaited?
> 
> Thanks in advance,
> Cobalt

[4] [encode/starlette #940](https://github.com/Kludex/starlette/issues/940#issuecomment-663784511) ? comment; similarity 0.542238919204

> Repository: encode/starlette
> Issue: #940
> Title: WebSocket max connection pool size ?
> 
> Unfortunately my code is for my company so I can't share it directly, I can try to come up with a minimum reproducible example for demo purposes. I will say that the functionality of the service I'm building is unique, we aren't broadcasting out to all connected clients, only ever one at a time. Essentially, I'll have 2000+ connected websocket clients and then I expose an API that allows you to send a message to a connected client via an API endpoint. Doing this, I can easily connect 2000+ websocket clients and send 200k+ messages to them from 50+ workers who are generated random messages without any hiccups at all.

[5] [encode/starlette #969](https://github.com/Kludex/starlette/issues/969#issuecomment-645137871) ? comment; similarity 0.541254709356

> Repository: encode/starlette
> Issue: #969
> Title: Is it okay to use sqlalchemy in async mode without using databases?
> 
> In addition to Gino, you can also use Sqlalchemy core with [`asyncpg`](https://magicstack.github.io/asyncpg/current/) as well as [`asyncpgsa`](https://asyncpgsa.readthedocs.io/en/latest/). This is less ORM-ish, though, and more towards using Sqlalchemy core to build up your queries, which get executed by a connection object.

### heldout-encode-multipart-integrity

Which Starlette multipart upload design verifies a client-provided SHA-256 incrementally, resumes an interrupted upload at a byte offset, and guarantees no duplicate bytes in the stored file?

Score: 0.591637835246; cutoff decision: **passed**. Label ambiguous: **False**.

Upload customization, streaming and size-limit discussions do not establish the combined checksum/resume/no-duplicate-byte protocol. Model abstained.

Allocated embedding cost: $0.00000072 (36 tokens). Generation cost: $0.00007725. Total token cost: $0.00007797. Generation usage: `{"completion_tokens": 92, "prompt_tokens": 809, "total_tokens": 901, "completion_tokens_details": {"accepted_prediction_tokens": 0, "audio_tokens": 0, "reasoning_tokens": 0, "rejected_prediction_tokens": 0}, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": null, "cached_tokens": 0}}`.

**Generated response**

The retrieved excerpts do not contain any information describing a Starlette multipart upload design that (a) verifies a client-provided SHA-256 incrementally, (b) resumes an interrupted upload at a byte offset, and (c) guarantees no duplicate bytes in the stored file. Therefore, I cannot determine an answer from the provided sources. If you can share a more relevant issue or excerpt, I can reassess.

**Retrieved citations and complete evidence**

[1] [encode/starlette #849](https://github.com/Kludex/starlette/issues/849#issuecomment-592348734) ? comment; similarity 0.591637835246

> Repository: encode/starlette
> Issue: #849
> Title: Possible to parse uploaded files while they are being uploaded?
> 
> Similar discussions in #697 and #388 (which I participated in and then forgot about!)

[2] [encode/starlette #697](https://github.com/Kludex/starlette/issues/697#issuecomment-547760582) ? comment; similarity 0.583623576759

> Repository: encode/starlette
> Issue: #697
> Title: Add option to overwrite UploadFile impl
> 
> @canni there's a similar question in https://github.com/encode/starlette/issues/388 if it can be of any help.

[3] [encode/starlette #579](https://github.com/Kludex/starlette/issues/579#issuecomment-511781994) ? comment; similarity 0.554274998209

> Repository: encode/starlette
> Issue: #579
> Title: UploadFile hogs RAM
> 
> PR ready.

[4] [tiangolo/fastapi #5413](https://github.com/fastapi/fastapi/issues/5413#issuecomment-1254208101) ? comment; similarity 0.539963314964

> Repository: tiangolo/fastapi
> Issue: #5413
> Title: upload file of multiple files of 256M is very slow
> 
> How is it with pure Starlette?

[5] [encode/starlette #2785](https://github.com/Kludex/starlette/issues/2785#issuecomment-2523020952) ? comment; similarity 0.537875601192

> Repository: encode/starlette
> Issue: #2785
> Title: MultiPartException: Part exceeded maximum size 1M
> 
> PR welcome to customize it, or use the default value.

### heldout-encode-cors-policy-proof

What indexed Starlette issue proves a dynamically reloaded per-tenant CORS policy cannot leak one tenant's allowed origins to another during concurrent configuration updates?

Score: 0.675556998816; cutoff decision: **passed**. Label ambiguous: **False**.

CORS origins, cacheability, and a reported leak are related, but none proves isolation for concurrent dynamic per-tenant policy reloads. Model abstained.

Allocated embedding cost: $0.00000058 (29 tokens). Generation cost: $0.00010700. Total token cost: $0.00010758. Generation usage: `{"completion_tokens": 134, "prompt_tokens": 1068, "total_tokens": 1202, "completion_tokens_details": {"accepted_prediction_tokens": 0, "audio_tokens": 0, "reasoning_tokens": 0, "rejected_prediction_tokens": 0}, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": null, "cached_tokens": 0}}`.

**Generated response**

From the retrieved issues, there isn’t a clear, indexed Starlette issue that proves a dynamically reloaded per-tenant CORS policy cannot leak origins between tenants during concurrent updates. The excerpts discuss CORS behavior in general (e.g., per-request origin handling, credentialed requests, and potential leakage concerns) but do not provide a concrete, indexed issue that proves this specific concurrency/isolation property.

If you want a precise citation, none of the provided excerpts definitively establish that guarantee. You may need to reference a separate, more targeted issue or a definitive test/PR in Starlette or the related CORS middleware.

**Retrieved citations and complete evidence**

[1] [encode/starlette #1309](https://github.com/Kludex/starlette/issues/1309) ? heuristic_resolution; similarity 0.675556998816

> Repository: encode/starlette
> Issue: #1309
> Title: Multiple values for access-control-allow-origin
> 
> [Low-confidence heuristic resolution; not ground truth. Stored confidence: low]
> > For this particular issue, the fix needed is to use exactly one of starlette or engine.io to handle CORS, as noted earlier.
> 
> If that's the case, I don't think we have an issue on Starlette.

[2] [encode/starlette #95](https://github.com/Kludex/starlette/issues/95) ? issue_body; similarity 0.645247860289

> Repository: encode/starlette
> Issue: #95
> Title: Credentialed CORS standard requests should not respond with wildcard origins
> 
> See https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS#Credentialed_requests_and_wildcards 
> 
> If a standard request is made, that includes any cookie headers, then CORSMiddleware *ought* to strictly respond with the requested origin, rather than a wildcard.
> 
> This is actually potentially a bit fiddly since we maybe also need to make sure to *set or add* Vary: Origin in those cases, in order to ensure correct cacheability.

[3] [encode/starlette #510](https://github.com/Kludex/starlette/issues/510#issuecomment-491836700) ? comment; similarity 0.639592849584

> Repository: encode/starlette
> Issue: #510
> Title: 'access-control-allow-origin' header seems to "leak" between requests
> 
> Re "cookies": the var here is not used: https://github.com/blueyed/starlette/blob/1fc5cee3d603fa917facf66cf8259c5e05635c10/starlette/middleware/cors.py#L101

[4] [encode/starlette #94](https://github.com/Kludex/starlette/issues/94#issuecomment-428250453) ? comment; similarity 0.626601462830

> Repository: encode/starlette
> Issue: #94
> Title: Option to enforce CORS server-side
> 
> (And since our handling is correct and in-line with most other implementations)

[5] [encode/starlette #34](https://github.com/Kludex/starlette/issues/34#issuecomment-409488042) ? comment; similarity 0.605214022884

> Repository: encode/starlette
> Issue: #34
> Title: CORS support
> 
> Thinking about this a bit more, what may be most important, at least for my understanding, is determining a potential view pattern. From what I can gather looking at the CORS extensions for other projects (including both WSGI and asyncio) is that they generally assume some application-level configuration but also that a wrapped application will return a mutable response.  
> 
> I can potentially see how to implement generic CORS behavior for Starlette in a similar way if I base it around something like the pattern proposed in https://github.com/encode/starlette/pull/35, but I haven't thought of an alternative as of yet.

### heldout-pydantic-validator-benchmark

What measured speedup do the indexed Pydantic issues report for a 50-field discriminated union with three nested model levels over 10 million records on an ARM64 2-vCPU host?

Score: 0.632746051557; cutoff decision: **passed**. Label ambiguous: **False**.

Discriminated-union performance issues are present; no requested 50-field, 3-level, 10-million-record ARM64 benchmark. Model did not invent a speedup.

Allocated embedding cost: $0.00000080 (40 tokens). Generation cost: $0.00008520. Total token cost: $0.00008600. Generation usage: `{"completion_tokens": 77, "prompt_tokens": 1088, "total_tokens": 1165, "completion_tokens_details": {"accepted_prediction_tokens": 0, "audio_tokens": 0, "reasoning_tokens": 0, "rejected_prediction_tokens": 0}, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": null, "cached_tokens": 0}}`.

**Generated response**

The retrieved excerpts do not contain any measured speedup data for a 50-field discriminated union with three nested model levels over 10 million records on an ARM64 2-vCPU host. If you have a link to the specific comment or issue containing that benchmark, I can quote it directly. [No sufficient evidence in provided sources]

**Retrieved citations and complete evidence**

[1] [pydantic/pydantic #12800](https://github.com/pydantic/pydantic/issues/12800#issuecomment-3984220759) ? comment; similarity 0.632746051557

> Repository: pydantic/pydantic
> Issue: #12800
> Title: Exponential perfomance drop (100k%) for edge cases serialization in `pydantic>=2.11.0b1` (0.044 seconds -> 183.207 seconds)
> 
> @davidhewitt will look into this in more depth. From what we discussed, trying all discriminated union members was most likely done to preserve some compatibility with normal unions, but I don't think it really makes sense to do so given that in theory other union members shouldn't serialize as well due to the discriminator value being different.
> 
> If we change the serialization logic, we should be careful adapting it when we tackle https://github.com/pydantic/pydantic/issues/11188.
> 
> Apart from the serialization behavior, we should also look into why the wrap serializer affects performance, and if https://github.com/pydantic/pydantic-core/pull/1652 is relevant.

[2] [pydantic/pydantic #8709](https://github.com/pydantic/pydantic/issues/8709#issuecomment-1930017282) ? comment; similarity 0.598262809233

> Repository: pydantic/pydantic
> Issue: #8709
> Title: Recursive model with discriminated union has exponential time and space complexity for validation
> 
> @palle-k,
> 
> Thanks for reporting this. @davidhewitt, could you please take a look at this performance issue when you have a chance? Thank you!

[3] [pydantic/pydantic #8953](https://github.com/pydantic/pydantic/issues/8953) ? issue_body; similarity 0.594976150931

> Repository: pydantic/pydantic
> Issue: #8953
> Title: Add performance tests for schema building + data validation -- discriminated union edition
> 
> We've been working on improvements to the discriminated union application logic. It'd be helpful to have performance tests associated with the schema building, as well as for validation against models with discriminated unions!

[4] [pydantic/pydantic #9458](https://github.com/pydantic/pydantic/issues/9458#issuecomment-2264174183) ? comment; similarity 0.583234117946

> Repository: pydantic/pydantic
> Issue: #9458
> Title: `isinstance` for v2 models is over 20 times slower than v1 models
> 
> Good news! We've got a big speedup now. These are the results on `main`:
> 

[5] [pydantic/pydantic #9908](https://github.com/pydantic/pydantic/issues/9908#issuecomment-2263864336) ? comment; similarity 0.578659099108

> Repository: pydantic/pydantic
> Issue: #9908
> Title: Extremely slow model imports
> 
> @ofek,
> 
> Huh, that's odd. We've been seeing improvements in our benchmarks for import time as well as schema build time...

### heldout-pydantic-migration-proof

Which indexed Pydantic migration procedure proves byte-for-byte identical JSON serialization between v1 and v2 for recursive generics, custom encoders, aliases, and timezone-aware datetimes together?

Score: 0.621116224981; cutoff decision: **passed**. Label ambiguous: **False**.

Serialization behavior differences and migration discussions do not supply the requested combined byte-for-byte equivalence proof. Model abstained.

Allocated embedding cost: $0.00000074 (37 tokens). Generation cost: $0.00009685. Total token cost: $0.00009759. Generation usage: `{"completion_tokens": 120, "prompt_tokens": 977, "total_tokens": 1097, "completion_tokens_details": {"accepted_prediction_tokens": 0, "audio_tokens": 0, "reasoning_tokens": 0, "rejected_prediction_tokens": 0}, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": null, "cached_tokens": 0}}`.

**Generated response**

Based on the retrieved evidence, there is no explicit statement identifying a single indexed Pydantic migration procedure that proves byte-for-byte identical JSON serialization between v1 and v2 for all of: recursive generics, custom encoders, aliases, and timezone-aware datetimes together. The excerpts discuss related topics (serialization behavior changes, serialisers, exporting/dumping, and performance) but do not provide a concrete, combined proof procedure matching all four criteria. If you need a precise answer, please provide additional sources or specify a single procedure referenced in the issues.

**Retrieved citations and complete evidence**

[1] [pydantic/pydantic #6726](https://github.com/pydantic/pydantic/issues/6726#issuecomment-1659164245) ? comment; similarity 0.621116224981

> Repository: pydantic/pydantic
> Issue: #6726
> Title: Appropriate replacement for json_encoders
> 
> Indeed. It’s not exactly a 1:1 reproduction of the v1 behavior. Reproducing that particular behavior would make serialization considerably slower for every case because we’d have to check every single value.

[2] [pydantic/pydantic #4255](https://github.com/pydantic/pydantic/issues/4255#issuecomment-1200396911) ? comment; similarity 0.615867775019

> Repository: pydantic/pydantic
> Issue: #4255
> Title: Change in behaviour with JSON serialization between v1.8.2 and v1.9.1
> 
> I think that makes complete sense.
> 
> I haven't started working (or thinking) on how we do exporting/dumping in v2/pydantic-core but imagine it'll be somewhat similar to validation where we have a linked collection of serialisers, a functional serialiser would accomplish exactly what you need.

[3] [pydantic/pydantic #5771](https://github.com/pydantic/pydantic/issues/5771#issuecomment-1550088058) ? comment; similarity 0.603085782324

> Repository: pydantic/pydantic
> Issue: #5771
> Title: V1 inside V2 for migration purposes
> 
> Excellent.  Then this is exactly what I was asking for.  Much appreciated

[4] [pydantic/pydantic #6895](https://github.com/pydantic/pydantic/issues/6895#issuecomment-1656204691) ? comment; similarity 0.598406333621

> Repository: pydantic/pydantic
> Issue: #6895
> Title: Generic model without arguments leads to serialization data loss after V2
> 
> > SerializeAsAny behavior automatically when attributes are typevars that are falling back to non-parametrized default values
> 
> Does it incur then some "hidden" performance penalty btw?

[5] [pydantic/pydantic #7001](https://github.com/pydantic/pydantic/issues/7001#issuecomment-1856593120) ? comment; similarity 0.596046473476

> Repository: pydantic/pydantic
> Issue: #7001
> Title: JSON serialization performance decrease when upgrading from 2.0.3 to 2.1.1
> 
> Closing this for now, we're onto more efficient versions and way past `2.1.1`.

### heldout-pydantic-settings-secret-rotation

How do indexed Pydantic settings issues rotate encrypted secrets across multiple running processes atomically while preserving rollback to the previous key after a failed deployment?

Score: 0.492061743516; cutoff decision: **refused**. Label ambiguous: **False**.

Only cutoff refusal. Retrieved SecretStr and settings-source discussions do not specify atomic encrypted multi-process rotation with failed-deployment rollback. No generation call was made.

Allocated embedding cost: $0.00000058 (29 tokens). Generation cost: $0.00000000. Total token cost: $0.00000058. Generation usage: `null`.

**Generated response**

Not generated; refused by cutoff.

**Retrieved citations and complete evidence**

[1] [pydantic/pydantic #596](https://github.com/pydantic/pydantic/issues/596#issuecomment-503131749) ? comment; similarity 0.492061743516

> Repository: pydantic/pydantic
> Issue: #596
> Title: Configurable SecretStr
> 
> > The environment in which you're processing "secret" values has to be trusted, so why not just use str
> 
> For example it can be a breach of data policy to log patient identifiable information. The trust levels between a tightly controlled internal database and, say, an external service Datadog, are far from equal.
> 
> Yet, in dev, it can be very helpful to see this to help understand what is going on. We try to keep this kind of information at `debug` level and in prod keep log level at info. However, two layers of protection are good. In an emergency on prod where we had to enable debug logs, or, a configuration mistake, secrets would still be shielded from exposure.

[2] [pydantic/pydantic #1279](https://github.com/pydantic/pydantic/issues/1279#issuecomment-668330407) ? comment; similarity 0.488490667826

> Repository: pydantic/pydantic
> Issue: #1279
> Title: Read values from secrets files when using BaseSettings
> 
> @FichteFoll I see your comment about "secrets override values from env", I was wondering on how you would achieve the opposite.

[3] [pydantic/pydantic #607](https://github.com/pydantic/pydantic/issues/607) ? issue_body; similarity 0.481483742817

> Repository: pydantic/pydantic
> Issue: #607
> Title: .env file like crea when using BaseSettings
> 
> so secrets can be kept out of git without having to always activate an environment.

[4] [pydantic/pydantic #1044](https://github.com/pydantic/pydantic/issues/1044#issuecomment-616115059) ? comment; similarity 0.470770730269

> Repository: pydantic/pydantic
> Issue: #1044
> Title: Should `SecretStr` be idempotent?
> 
> Thanks so much.

[5] [pydantic/pydantic #4001](https://github.com/pydantic/pydantic/issues/4001#issuecomment-1106921956) ? comment; similarity 0.453792057373

> Repository: pydantic/pydantic
> Issue: #4001
> Title: BaseSettings does not work with hyphens in secrets file name.
> 
> Please provide a self contained example of the problem.

### heldout-pydantic-schema-lossless-roundtrip

Which Pydantic implementation in the indexed issues provides lossless JSON Schema to model to JSON Schema round-tripping, including recursive references, custom validators, and field ordering?

Score: 0.679250281673; cutoff decision: **passed**. Label ambiguous: **True**.

AMBIGUOUS: Pydantic #1855 explicitly says JSON Schema does not encode custom validations. This supports a negative response to the requested lossless round-trip premise, although no full implementation is supplied. Model abstained. Do not count the provisional label as established unanswerability.

Allocated embedding cost: $0.00000068 (34 tokens). Generation cost: $0.00009800. Total token cost: $0.00009868. Generation usage: `{"completion_tokens": 121, "prompt_tokens": 992, "total_tokens": 1113, "completion_tokens_details": {"accepted_prediction_tokens": 0, "audio_tokens": 0, "reasoning_tokens": 0, "rejected_prediction_tokens": 0}, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": null, "cached_tokens": 0}}`.

**Generated response**

The retrieved excerpts do not contain a definitive statement about a Pydantic implementation that provides lossless JSON Schema to model to JSON Schema round-tripping (including recursive references, custom validators, and field ordering). None of the cited issues directly claim such a capability.

Based on the provided sources:
- No excerpt explicitly describes a round-tripping implementation with those exact features. [1][2][3][4][5]

If you want a precise answer, please share additional relevant issues or links that discuss a JSON Schema to model to JSON Schema round-trip capability.

**Retrieved citations and complete evidence**

[1] [pydantic/pydantic #11723](https://github.com/pydantic/pydantic/issues/11723#issuecomment-2788853626) ? comment; similarity 0.679250281673

> Repository: pydantic/pydantic
> Issue: #11723
> Title: SkipJsonSchema[None] + Field Validation creates a rabbit hole to dig
> 
> maybe duplicated #11500

[2] [pydantic/pydantic #129](https://github.com/pydantic/pydantic/issues/129) ? issue_body; similarity 0.668466092957

> Repository: pydantic/pydantic
> Issue: #129
> Title: Support for JSON-Schema?
> 
> I'm wondering if there's been any investigation into translating Pydantic models into json schemas? The use-case for us is simply to expose the schemas to users in our frontend. We're happy to build this ourselves, but just want to check if it's something that is seen as within the scope of the project.

[3] [pydantic/pydantic #4697](https://github.com/pydantic/pydantic/issues/4697#issuecomment-2881685671) ? comment; similarity 0.661323096468

> Repository: pydantic/pydantic
> Issue: #4697
> Title: JSON Schema for serialised model, rather than data required for validation
> 
> @mattschmitz Pydantic changed its treatment of the defaults afterwards (from version `2.3.0` to `2.4.0`). The reasons for that change and possible workarounds are summarised here: https://github.com/pydantic/pydantic/issues/8413#issuecomment-1864737517

[4] [pydantic/pydantic #4666](https://github.com/pydantic/pydantic/issues/4666#issuecomment-1294855274) ? comment; similarity 0.653983688185

> Repository: pydantic/pydantic
> Issue: #4666
> Title: V2: JSON Schema
> 
> Need to think about #1270 while working on this, it has a lot of interest.

[5] [pydantic/pydantic #1855](https://github.com/pydantic/pydantic/issues/1855#issuecomment-689651212) ? comment; similarity 0.649926581314

> Repository: pydantic/pydantic
> Issue: #1855
> Title: Access pydantic models for code generation to other languages
> 
> Somewhat related:
> We use [the json schema functionality](https://pydantic-docs.helpmanual.io/usage/schema/) to generate a form in the frontend. I am not sure if that satisfies your requirements, but it is an implementation and the json schema generally encode quite a lot of the constraints (not custom validations though)

### heldout-pydantic-validator-sandbox

Which Pydantic validator configuration safely executes tenant-supplied Python validation code with enforced CPU and memory limits and a documented sandbox escape analysis?

Score: 0.589108822913; cutoff decision: **passed**. Label ambiguous: **False**.

Validator reuse and async/exception discussions do not describe a tenant-code sandbox with CPU/memory enforcement and an escape analysis. Model abstained.

Allocated embedding cost: $0.00000054 (27 tokens). Generation cost: $0.00008385. Total token cost: $0.00008439. Generation usage: `{"completion_tokens": 94, "prompt_tokens": 925, "total_tokens": 1019, "completion_tokens_details": {"accepted_prediction_tokens": 0, "audio_tokens": 0, "reasoning_tokens": 0, "rejected_prediction_tokens": 0}, "prompt_tokens_details": {"audio_tokens": 0, "cache_write_tokens": null, "cached_tokens": 0}}`.

**Generated response**

The retrieved excerpts do not contain any information about a Pydantic validator configuration that safely executes tenant-supplied Python validation code with enforced CPU and memory limits and a documented sandbox escape analysis. None of the cited issues discuss sandboxing, resource limits, or escape analysis. Therefore, I cannot provide an answer based on the provided sources. If you have additional excerpts or a link to the relevant discussion, I can review them.

**Retrieved citations and complete evidence**

[1] [pydantic/pydantic #897](https://github.com/pydantic/pydantic/issues/897#issuecomment-1695457531) ? comment; similarity 0.589108822913

> Repository: pydantic/pydantic
> Issue: #897
> Title: Disable all validations
> 
> How to skip validation in v2.3.0?

[2] [pydantic/pydantic #940](https://github.com/pydantic/pydantic/issues/940#issuecomment-569772370) ? comment; similarity 0.586484087641

> Repository: pydantic/pydantic
> Issue: #940
> Title: Re-use validators?
> 
> (thanks for reminding us it's not documented)

[3] [pydantic/pydantic #932](https://github.com/pydantic/pydantic/issues/932#issuecomment-561158394) ? comment; similarity 0.584739785470

> Repository: pydantic/pydantic
> Issue: #932
> Title: Skip values that don't pass validation
> 
> That code works fine, I'm using it in production. Please explain in more detail the problem you're having.

[4] [pydantic/pydantic #3915](https://github.com/pydantic/pydantic/issues/3915#issuecomment-1216623588) ? comment; similarity 0.574427735737

> Repository: pydantic/pydantic
> Issue: #3915
> Title: Exception handling during validation
> 
> We have the new system of validators, including wrap validators in V2.
> 
> https://pydantic-docs.helpmanual.io/blog/pydantic-v2/#validator-function-improvements

[5] [pydantic/pydantic #857](https://github.com/pydantic/pydantic/issues/857#issuecomment-729044640) ? comment; similarity 0.569182573674

> Repository: pydantic/pydantic
> Issue: #857
> Title: Is it possible to use async methods as validators?
> 
> @samuelcolvin Integrating Pydantic + Tortoise (async ORM) + FastAPI (async), how would you recommend one go about validating entries in the database? Validating database relationships/entries via Pydantic interface makes sense to me, but I'm no contributor or expert of the source.
> 
> From my understanding, the [`@validate_arguments`](https://pydantic-docs.helpmanual.io/usage/validation_decorator/#async-functions) decorator has asynchronous support, so why wouldn't the `@validator` have the same?

## Reproduction and stopping point

`python -m unittest discover -s tests -q` runs local checks. The paid runner is `scripts/run_heldout_unanswerables.py --approved-budget-usd 0.02`; existing results/cache deliberately block repeated paid runs. Embeddings are cached in a git-ignored local file. Reuse them for any future read-only inspection rather than embedding again. No rerun or next checkpoint is authorized here. All 79 tests pass. Stop for user review.

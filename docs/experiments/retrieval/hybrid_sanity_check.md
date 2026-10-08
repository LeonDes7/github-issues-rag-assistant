# Hybrid sanity check

Top-five lists are saved baseline outputs; FTS counts and plans are live read-only checks. Full hybrid execution plans use an existing corpus embedding as a diagnostic probe, NOT a question embedding or eval rerun. No OpenAI calls.

| Case | FTS matches | Vector top 5 | Hybrid top 5 | Different positions |
|---|---:|---|---|---|
| generated-encode-starlette-1119 | 0 | tiangolo/fastapi#4108, tiangolo/fastapi#793, tiangolo/fastapi#5291, tiangolo/fastapi#793, tiangolo/fastapi#793 | tiangolo/fastapi#4108, tiangolo/fastapi#793, tiangolo/fastapi#5291, tiangolo/fastapi#793, tiangolo/fastapi#793 | none |
| generated-encode-starlette-408 | 0 | encode/starlette#408, encode/starlette#408, encode/starlette#671, encode/starlette#671, encode/starlette#763 | encode/starlette#408, encode/starlette#408, encode/starlette#671, encode/starlette#671, encode/starlette#763 | none |
| generated-encode-starlette-542 | 0 | encode/starlette#542, encode/starlette#542, encode/starlette#542, encode/starlette#542, encode/starlette#1144 | encode/starlette#542, encode/starlette#542, encode/starlette#542, encode/starlette#542, encode/starlette#1144 | none |
| generated-tiangolo-fastapi-2071 | 0 | encode/starlette#407, encode/starlette#1369, encode/starlette#940, encode/starlette#407, encode/starlette#940 | encode/starlette#407, encode/starlette#1369, encode/starlette#940, encode/starlette#407, encode/starlette#940 | none |
| generated-encode-starlette-383 | 0 | encode/starlette#383, encode/starlette#383, encode/starlette#814, encode/starlette#814, encode/starlette#383 | encode/starlette#383, encode/starlette#383, encode/starlette#814, encode/starlette#814, encode/starlette#383 | none |
| generated-tiangolo-fastapi-618 | 0 | tiangolo/fastapi#618, tiangolo/fastapi#759, tiangolo/fastapi#618, tiangolo/fastapi#618, tiangolo/fastapi#618 | tiangolo/fastapi#618, tiangolo/fastapi#759, tiangolo/fastapi#618, tiangolo/fastapi#618, tiangolo/fastapi#618 | none |
| generated-pydantic-pydantic-4598 | 0 | pydantic/pydantic#1626, pydantic/pydantic#3295, pydantic/pydantic#3710, pydantic/pydantic#1626, pydantic/pydantic#1626 | pydantic/pydantic#1626, pydantic/pydantic#3295, pydantic/pydantic#3710, pydantic/pydantic#1626, pydantic/pydantic#1626 | none |
| generated-pydantic-pydantic-7461 | 0 | tiangolo/fastapi#1909, tiangolo/fastapi#1909, encode/starlette#1175, tiangolo/fastapi#227, encode/starlette#1116 | tiangolo/fastapi#1909, tiangolo/fastapi#1909, encode/starlette#1175, tiangolo/fastapi#227, encode/starlette#1116 | none |
| generated-tiangolo-fastapi-1873 | 0 | tiangolo/fastapi#656, tiangolo/fastapi#4893, tiangolo/fastapi#1873, tiangolo/fastapi#656, tiangolo/fastapi#656 | tiangolo/fastapi#656, tiangolo/fastapi#4893, tiangolo/fastapi#1873, tiangolo/fastapi#656, tiangolo/fastapi#656 | none |
| generated-tiangolo-fastapi-5108 | 0 | tiangolo/fastapi#5676, tiangolo/fastapi#5676, tiangolo/fastapi#2350, tiangolo/fastapi#5676, tiangolo/fastapi#5676 | tiangolo/fastapi#5676, tiangolo/fastapi#5676, tiangolo/fastapi#2350, tiangolo/fastapi#5676, tiangolo/fastapi#5676 | none |
| generated-pydantic-pydantic-11555 | 0 | pydantic/pydantic#11555, pydantic/pydantic#11555, pydantic/pydantic#8548, pydantic/pydantic#10445, pydantic/pydantic#7042 | pydantic/pydantic#11555, pydantic/pydantic#11555, pydantic/pydantic#8548, pydantic/pydantic#10445, pydantic/pydantic#7042 | none |
| generated-tiangolo-fastapi-5370 | 0 | tiangolo/fastapi#5370, tiangolo/fastapi#5370, tiangolo/fastapi#5370, tiangolo/fastapi#5370, tiangolo/fastapi#253 | tiangolo/fastapi#5370, tiangolo/fastapi#5370, tiangolo/fastapi#5370, tiangolo/fastapi#5370, tiangolo/fastapi#253 | none |
| generated-pydantic-pydantic-5946 | 0 | pydantic/pydantic#5946, pydantic/pydantic#5946, pydantic/pydantic#5946, pydantic/pydantic#5946, pydantic/pydantic#5946 | pydantic/pydantic#5946, pydantic/pydantic#5946, pydantic/pydantic#5946, pydantic/pydantic#5946, pydantic/pydantic#5946 | none |
| generated-encode-starlette-953 | 0 | encode/starlette#953, encode/starlette#970, encode/starlette#970, encode/starlette#970, encode/starlette#953 | encode/starlette#953, encode/starlette#970, encode/starlette#970, encode/starlette#970, encode/starlette#953 | none |
| generated-tiangolo-fastapi-5988 | 0 | tiangolo/fastapi#2349, tiangolo/fastapi#782, tiangolo/fastapi#3028, tiangolo/fastapi#782, tiangolo/fastapi#5988 | tiangolo/fastapi#2349, tiangolo/fastapi#782, tiangolo/fastapi#3028, tiangolo/fastapi#782, tiangolo/fastapi#5988 | none |
| generated-pydantic-pydantic-8499 | 0 | pydantic/pydantic#8499, pydantic/pydantic#8499, pydantic/pydantic#8499, pydantic/pydantic#8499, pydantic/pydantic#8499 | pydantic/pydantic#8499, pydantic/pydantic#8499, pydantic/pydantic#8499, pydantic/pydantic#8499, pydantic/pydantic#8499 | none |
| generated-encode-starlette-1247 | 0 | encode/starlette#1247, encode/starlette#1247, encode/starlette#1247, encode/starlette#1247, encode/starlette#1247 | encode/starlette#1247, encode/starlette#1247, encode/starlette#1247, encode/starlette#1247, encode/starlette#1247 | none |
| generated-pydantic-pydantic-10995 | 0 | pydantic/pydantic#10995, pydantic/pydantic#10995, pydantic/pydantic#10995, pydantic/pydantic#10995, pydantic/pydantic#10995 | pydantic/pydantic#10995, pydantic/pydantic#10995, pydantic/pydantic#10995, pydantic/pydantic#10995, pydantic/pydantic#10995 | none |
| generated-encode-starlette-494 | 0 | encode/starlette#494, encode/starlette#494, encode/starlette#494, encode/starlette#494, encode/starlette#494 | encode/starlette#494, encode/starlette#494, encode/starlette#494, encode/starlette#494, encode/starlette#494 | none |
| generated-pydantic-pydantic-9575 | 0 | pydantic/pydantic#9575, pydantic/pydantic#9575, pydantic/pydantic#9575, pydantic/pydantic#7790, pydantic/pydantic#8818 | pydantic/pydantic#9575, pydantic/pydantic#9575, pydantic/pydantic#9575, pydantic/pydantic#7790, pydantic/pydantic#8818 | none |
| generated-tiangolo-fastapi-10999 | 0 | tiangolo/fastapi#10999, tiangolo/fastapi#10999, tiangolo/fastapi#10999, tiangolo/fastapi#10999, tiangolo/fastapi#10999 | tiangolo/fastapi#10999, tiangolo/fastapi#10999, tiangolo/fastapi#10999, tiangolo/fastapi#10999, tiangolo/fastapi#10999 | none |
| generated-pydantic-pydantic-10131 | 0 | pydantic/pydantic#10131, pydantic/pydantic#10131, pydantic/pydantic#10131, pydantic/pydantic#10131, pydantic/pydantic#10131 | pydantic/pydantic#10131, pydantic/pydantic#10131, pydantic/pydantic#10131, pydantic/pydantic#10131, pydantic/pydantic#10131 | none |
| generated-pydantic-pydantic-5997 | 0 | pydantic/pydantic#5997, pydantic/pydantic#5997, pydantic/pydantic#5997, pydantic/pydantic#5997, pydantic/pydantic#5997 | pydantic/pydantic#5997, pydantic/pydantic#5997, pydantic/pydantic#5997, pydantic/pydantic#5997, pydantic/pydantic#5997 | none |
| generated-encode-starlette-1295 | 0 | encode/starlette#1295, encode/starlette#58, tiangolo/fastapi#166, tiangolo/fastapi#166, tiangolo/fastapi#166 | encode/starlette#1295, encode/starlette#58, tiangolo/fastapi#166, tiangolo/fastapi#166, tiangolo/fastapi#166 | none |
| generated-encode-starlette-127 | 0 | encode/starlette#127, tiangolo/fastapi#9614, tiangolo/fastapi#9614, tiangolo/fastapi#1292, tiangolo/fastapi#2625 | encode/starlette#127, tiangolo/fastapi#9614, tiangolo/fastapi#9614, tiangolo/fastapi#1292, tiangolo/fastapi#2625 | none |
| generated-encode-starlette-94 | 0 | encode/starlette#94, encode/starlette#94, encode/starlette#94, encode/starlette#34, encode/starlette#94 | encode/starlette#94, encode/starlette#94, encode/starlette#94, encode/starlette#34, encode/starlette#94 | none |
| generated-pydantic-pydantic-1060 | 0 | pydantic/pydantic#1060, pydantic/pydantic#6261, pydantic/pydantic#6261, pydantic/pydantic#6261, pydantic/pydantic#5377 | pydantic/pydantic#1060, pydantic/pydantic#6261, pydantic/pydantic#6261, pydantic/pydantic#6261, pydantic/pydantic#5377 | none |
| generated-pydantic-pydantic-4999 | 0 | pydantic/pydantic#1287, pydantic/pydantic#1287, pydantic/pydantic#1287, pydantic/pydantic#1287, pydantic/pydantic#2160 | pydantic/pydantic#1287, pydantic/pydantic#1287, pydantic/pydantic#1287, pydantic/pydantic#1287, pydantic/pydantic#2160 | none |
| generated-tiangolo-fastapi-33 | 0 | tiangolo/fastapi#1002, tiangolo/fastapi#1066, tiangolo/fastapi#33, tiangolo/fastapi#2374, tiangolo/fastapi#1066 | tiangolo/fastapi#1002, tiangolo/fastapi#1066, tiangolo/fastapi#33, tiangolo/fastapi#2374, tiangolo/fastapi#1066 | none |
| generated-encode-starlette-1004 | 0 | encode/starlette#1004, encode/starlette#1265, encode/starlette#1083, encode/starlette#1004, encode/starlette#1265 | encode/starlette#1004, encode/starlette#1265, encode/starlette#1083, encode/starlette#1004, encode/starlette#1265 | none |
| generated-encode-starlette-1454 | 0 | encode/starlette#1454, encode/starlette#1067, encode/starlette#1067, encode/starlette#1067, encode/starlette#650 | encode/starlette#1454, encode/starlette#1067, encode/starlette#1067, encode/starlette#1067, encode/starlette#650 | none |
| generated-pydantic-pydantic-4108 | 0 | pydantic/pydantic#1417, pydantic/pydantic#1417, pydantic/pydantic#1417, pydantic/pydantic#1164, pydantic/pydantic#1164 | pydantic/pydantic#1417, pydantic/pydantic#1417, pydantic/pydantic#1417, pydantic/pydantic#1164, pydantic/pydantic#1164 | none |
| generated-tiangolo-fastapi-1276 | 0 | tiangolo/fastapi#1276, tiangolo/fastapi#1276, tiangolo/fastapi#1276, tiangolo/fastapi#1276, tiangolo/fastapi#1276 | tiangolo/fastapi#1276, tiangolo/fastapi#1276, tiangolo/fastapi#1276, tiangolo/fastapi#1276, tiangolo/fastapi#1276 | none |
| generated-pydantic-pydantic-11865 | 0 | pydantic/pydantic#11865, pydantic/pydantic#11865, pydantic/pydantic#11746, pydantic/pydantic#10160, pydantic/pydantic#10160 | pydantic/pydantic#11865, pydantic/pydantic#11865, pydantic/pydantic#11746, pydantic/pydantic#10160, pydantic/pydantic#10160 | none |
| generated-pydantic-pydantic-9866 | 1 | pydantic/pydantic#9866, pydantic/pydantic#9866, pydantic/pydantic#9866, pydantic/pydantic#8575, pydantic/pydantic#9866 | pydantic/pydantic#9866, pydantic/pydantic#9866, pydantic/pydantic#9866, pydantic/pydantic#9866, pydantic/pydantic#8575 | 4, 5 |
| generated-tiangolo-fastapi-4268 | 0 | tiangolo/fastapi#4268, tiangolo/fastapi#4268, tiangolo/fastapi#4268, tiangolo/fastapi#4268, tiangolo/fastapi#4764 | tiangolo/fastapi#4268, tiangolo/fastapi#4268, tiangolo/fastapi#4268, tiangolo/fastapi#4268, tiangolo/fastapi#4764 | none |
| generated-encode-starlette-726 | 0 | encode/starlette#726, encode/starlette#726, encode/starlette#726, encode/starlette#437, encode/starlette#437 | encode/starlette#726, encode/starlette#726, encode/starlette#726, encode/starlette#437, encode/starlette#437 | none |
| generated-tiangolo-fastapi-5724 | 0 | tiangolo/fastapi#5724, tiangolo/fastapi#381, tiangolo/fastapi#5724, tiangolo/fastapi#381, tiangolo/fastapi#381 | tiangolo/fastapi#5724, tiangolo/fastapi#381, tiangolo/fastapi#5724, tiangolo/fastapi#381, tiangolo/fastapi#381 | none |
| generated-pydantic-pydantic-11491 | 0 | tiangolo/fastapi#518, tiangolo/fastapi#919, tiangolo/fastapi#919, tiangolo/fastapi#4747, tiangolo/fastapi#1217 | tiangolo/fastapi#518, tiangolo/fastapi#919, tiangolo/fastapi#919, tiangolo/fastapi#4747, tiangolo/fastapi#1217 | none |
| generated-tiangolo-fastapi-14502 | 0 | fastapi/fastapi#14496, tiangolo/fastapi#14500, tiangolo/fastapi#14499, tiangolo/fastapi#14497, tiangolo/fastapi#14501 | fastapi/fastapi#14496, tiangolo/fastapi#14500, tiangolo/fastapi#14499, tiangolo/fastapi#14497, tiangolo/fastapi#14501 | none |
| generated-tiangolo-fastapi-403 | 0 | tiangolo/fastapi#403, tiangolo/fastapi#2574, tiangolo/fastapi#2574, tiangolo/fastapi#2574, tiangolo/fastapi#483 | tiangolo/fastapi#403, tiangolo/fastapi#2574, tiangolo/fastapi#2574, tiangolo/fastapi#2574, tiangolo/fastapi#483 | none |
| generated-tiangolo-fastapi-261 | 0 | tiangolo/fastapi#261, tiangolo/fastapi#261, tiangolo/fastapi#1785, tiangolo/fastapi#261, tiangolo/fastapi#512 | tiangolo/fastapi#261, tiangolo/fastapi#261, tiangolo/fastapi#1785, tiangolo/fastapi#261, tiangolo/fastapi#512 | none |
| generated-encode-starlette-818 | 0 | encode/starlette#818, encode/starlette#818, encode/starlette#818, encode/starlette#818, encode/starlette#818 | encode/starlette#818, encode/starlette#818, encode/starlette#818, encode/starlette#818, encode/starlette#818 | none |
| generated-encode-starlette-855 | 0 | encode/starlette#855, tiangolo/fastapi#801, encode/starlette#855, encode/starlette#583, tiangolo/fastapi#754 | encode/starlette#855, tiangolo/fastapi#801, encode/starlette#855, encode/starlette#583, tiangolo/fastapi#754 | none |
| generated-tiangolo-fastapi-2776 | 0 | tiangolo/fastapi#2776, tiangolo/fastapi#2776, tiangolo/fastapi#2776, tiangolo/fastapi#2776, tiangolo/fastapi#2776 | tiangolo/fastapi#2776, tiangolo/fastapi#2776, tiangolo/fastapi#2776, tiangolo/fastapi#2776, tiangolo/fastapi#2776 | none |
| unanswerable-01 | 0 | pydantic/pydantic#6666, pydantic/pydantic#12220, pydantic/pydantic#8028, pydantic/pydantic#13173, pydantic/pydantic#12395 | pydantic/pydantic#6666, pydantic/pydantic#12220, pydantic/pydantic#8028, pydantic/pydantic#13173, pydantic/pydantic#12395 | none |
| unanswerable-02 | 0 | tiangolo/fastapi#364, tiangolo/fastapi#878, tiangolo/fastapi#4211, tiangolo/fastapi#2350, tiangolo/fastapi#401 | tiangolo/fastapi#364, tiangolo/fastapi#878, tiangolo/fastapi#4211, tiangolo/fastapi#2350, tiangolo/fastapi#401 | none |
| unanswerable-03 | 0 | pydantic/pydantic#3900, pydantic/pydantic#2587, pydantic/pydantic#960, pydantic/pydantic#960, pydantic/pydantic#2587 | pydantic/pydantic#3900, pydantic/pydantic#2587, pydantic/pydantic#960, pydantic/pydantic#960, pydantic/pydantic#2587 | none |
| unanswerable-04 | 0 | tiangolo/fastapi#1710, tiangolo/fastapi#2501, tiangolo/fastapi#551, encode/starlette#671, tiangolo/fastapi#545 | tiangolo/fastapi#1710, tiangolo/fastapi#2501, tiangolo/fastapi#551, encode/starlette#671, tiangolo/fastapi#545 | none |
| unanswerable-05 | 0 | pydantic/pydantic#4678, pydantic/pydantic#8652, pydantic/pydantic#8652, pydantic/pydantic#12696, pydantic/pydantic#6027 | pydantic/pydantic#4678, pydantic/pydantic#8652, pydantic/pydantic#8652, pydantic/pydantic#12696, pydantic/pydantic#6027 | none |
| unanswerable-06 | 0 | tiangolo/fastapi#4577, encode/starlette#2032, tiangolo/fastapi#5261, pydantic/pydantic#11103, pydantic/pydantic#8762 | tiangolo/fastapi#4577, encode/starlette#2032, tiangolo/fastapi#5261, pydantic/pydantic#11103, pydantic/pydantic#8762 | none |
| unanswerable-07 | 0 | tiangolo/fastapi#3297, tiangolo/fastapi#3297, encode/starlette#1790, tiangolo/fastapi#1781, tiangolo/fastapi#453 | tiangolo/fastapi#3297, tiangolo/fastapi#3297, encode/starlette#1790, tiangolo/fastapi#1781, tiangolo/fastapi#453 | none |
| unanswerable-08 | 0 | tiangolo/fastapi#2009, tiangolo/fastapi#2009, tiangolo/fastapi#2009, tiangolo/fastapi#2009, tiangolo/fastapi#2106 | tiangolo/fastapi#2009, tiangolo/fastapi#2009, tiangolo/fastapi#2009, tiangolo/fastapi#2009, tiangolo/fastapi#2106 | none |
| unanswerable-09 | 0 | tiangolo/fastapi#5882, encode/starlette#1082, pydantic/pydantic#6656, tiangolo/fastapi#3711, pydantic/pydantic#8652 | tiangolo/fastapi#5882, encode/starlette#1082, pydantic/pydantic#6656, tiangolo/fastapi#3711, pydantic/pydantic#8652 | none |
| unanswerable-10 | 0 | tiangolo/fastapi#1828, tiangolo/fastapi#149, tiangolo/fastapi#246, tiangolo/fastapi#149, tiangolo/fastapi#80 | tiangolo/fastapi#1828, tiangolo/fastapi#149, tiangolo/fastapi#246, tiangolo/fastapi#149, tiangolo/fastapi#80 | none |
| unanswerable-11 | 0 | encode/starlette#2664, encode/starlette#2664, tiangolo/fastapi#143, tiangolo/fastapi#2387, tiangolo/fastapi#5261 | encode/starlette#2664, encode/starlette#2664, tiangolo/fastapi#143, tiangolo/fastapi#2387, tiangolo/fastapi#5261 | none |
| unanswerable-12 | 0 | tiangolo/fastapi#3046, pydantic/pydantic#9880, pydantic/pydantic#5914, pydantic/pydantic#12801, tiangolo/fastapi#5063 | tiangolo/fastapi#3046, pydantic/pydantic#9880, pydantic/pydantic#5914, pydantic/pydantic#12801, tiangolo/fastapi#5063 | none |
| unanswerable-13 | 0 | encode/starlette#2010, encode/starlette#2010, encode/starlette#917, encode/starlette#50, encode/starlette#136 | encode/starlette#2010, encode/starlette#2010, encode/starlette#917, encode/starlette#50, encode/starlette#136 | none |
| unanswerable-14 | 0 | tiangolo/fastapi#3901, pydantic/pydantic#7170, tiangolo/fastapi#3711, tiangolo/fastapi#3711, tiangolo/fastapi#3711 | tiangolo/fastapi#3901, pydantic/pydantic#7170, tiangolo/fastapi#3711, tiangolo/fastapi#3711, tiangolo/fastapi#3711 | none |
| unanswerable-15 | 0 | tiangolo/fastapi#4838, tiangolo/fastapi#4877, tiangolo/fastapi#702, tiangolo/fastapi#5412, tiangolo/fastapi#702 | tiangolo/fastapi#4838, tiangolo/fastapi#4877, tiangolo/fastapi#702, tiangolo/fastapi#5412, tiangolo/fastapi#702 | none |

## generated-encode-starlette-1119

```text
Limit  (cost=788.29..788.30 rows=1 width=20) (actual time=2.832..2.834 rows=0.00 loops=1)
  Buffers: shared hit=232
  ->  Sort  (cost=788.29..788.30 rows=1 width=20) (actual time=2.831..2.832 rows=0.00 loops=1)
        Sort Key: (ts_rank_cd(search_vector, '''could'' & ''reason'' & ''receiv'' & ''405'' & ''method'' & ''allow'' & ''error'' & ''tri'' & ''access'' & ''/predict'' & ''endpoint'''::tsquery)) DESC, chunk_id
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=232
        ->  Bitmap Heap Scan on github_issue_chunks  (cost=784.27..788.28 rows=1 width=20) (actual time=2.796..2.797 rows=0.00 loops=1)
              Recheck Cond: (search_vector @@ '''could'' & ''reason'' & ''receiv'' & ''405'' & ''method'' & ''allow'' & ''error'' & ''tri'' & ''access'' & ''/predict'' & ''endpoint'''::tsquery)
              Buffers: shared hit=226
              ->  Bitmap Index Scan on github_issue_chunks_search_vector_gin_idx  (cost=0.00..784.27 rows=1 width=0) (actual time=2.782..2.783 rows=0.00 loops=1)
                    Index Cond: (search_vector @@ '''could'' & ''reason'' & ''receiv'' & ''405'' & ''method'' & ''allow'' & ''error'' & ''tri'' & ''access'' & ''/predict'' & ''endpoint'''::tsquery)
                    Index Searches: 1
                    Buffers: shared hit=226
Planning:
  Buffers: shared hit=38 read=4
  I/O Timings: shared read=2.638
Planning Time: 3.630 ms
Execution Time: 2.883 ms
```

## generated-encode-starlette-408

```text
Limit  (cost=801.26..801.27 rows=1 width=20) (actual time=2.794..2.795 rows=0.00 loops=1)
  Buffers: shared hit=215
  ->  Sort  (cost=801.26..801.27 rows=1 width=20) (actual time=2.793..2.794 rows=0.00 loops=1)
        Sort Key: (ts_rank_cd(search_vector, '''recommend'' & ''way'' & ''dump'' & ''set'' & ''starlette.config'' & ''without'' & ''expos'' & ''sensit'' & ''inform'' & ''like'' & ''jwt'' & ''secret'''::tsquery)) DESC, chunk_id
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=215
        ->  Bitmap Heap Scan on github_issue_chunks  (cost=797.24..801.25 rows=1 width=20) (actual time=2.788..2.788 rows=0.00 loops=1)
              Recheck Cond: (search_vector @@ '''recommend'' & ''way'' & ''dump'' & ''set'' & ''starlette.config'' & ''without'' & ''expos'' & ''sensit'' & ''inform'' & ''like'' & ''jwt'' & ''secret'''::tsquery)
              Buffers: shared hit=215
              ->  Bitmap Index Scan on github_issue_chunks_search_vector_gin_idx  (cost=0.00..797.23 rows=1 width=0) (actual time=2.778..2.778 rows=0.00 loops=1)
                    Index Cond: (search_vector @@ '''recommend'' & ''way'' & ''dump'' & ''set'' & ''starlette.config'' & ''without'' & ''expos'' & ''sensit'' & ''inform'' & ''like'' & ''jwt'' & ''secret'''::tsquery)
                    Index Searches: 1
                    Buffers: shared hit=215
Planning:
  Buffers: shared hit=1
Planning Time: 0.210 ms
Execution Time: 2.821 ms
```

## generated-encode-starlette-542

```text
Limit  (cost=762.36..762.36 rows=1 width=20) (actual time=2.311..2.312 rows=0.00 loops=1)
  Buffers: shared hit=204
  ->  Sort  (cost=762.36..762.36 rows=1 width=20) (actual time=2.311..2.311 rows=0.00 loops=1)
        Sort Key: (ts_rank_cd(search_vector, '''recommend'' & ''workaround'' & ''depend'' & ''issu'' & ''graphen'' & ''aniso8601'' & ''instal'' & ''starlett'' & ''full'''::tsquery)) DESC, chunk_id
        Sort Method: quicksort  Memory: 25kB
        Buffers: shared hit=204
        ->  Bitmap Heap Scan on github_issue_chunks  (cost=758.33..762.35 rows=1 width=20) (actual time=2.306..2.306 rows=0.00 loops=1)
              Recheck Cond: (search_vector @@ '''recommend'' & ''workaround'' & ''depend'' & ''issu'' & ''graphen'' & ''aniso8601'' & ''instal'' & ''starlett'' & ''full'''::tsquery)
              Buffers: shared hit=204
              ->  Bitmap Index Scan on github_issue_chunks_search_vector_gin_idx  (cost=0.00..758.33 rows=1 width=0) (actual time=2.295..2.296 rows=0.00 loops=1)
                    Index Cond: (search_vector @@ '''recommend'' & ''workaround'' & ''depend'' & ''issu'' & ''graphen'' & ''aniso8601'' & ''instal'' & ''starlett'' & ''full'''::tsquery)
                    Index Searches: 1
                    Buffers: shared hit=204
Planning:
  Buffers: shared hit=1
Planning Time: 0.205 ms
Execution Time: 2.339 ms
```

## Full hybrid diagnostic 1

```text
Limit  (cost=3471.57..3471.58 rows=5 width=773) (actual time=308.694..308.703 rows=5.00 loops=1)
  Buffers: shared hit=808 read=300
  I/O Timings: shared read=240.439
  ->  Sort  (cost=3471.57..3471.59 rows=6 width=773) (actual time=308.693..308.700 rows=5.00 loops=1)
        Sort Key: (LEAST(1.0, (sum((1.0 / ((60 + vector_results.rank))::numeric)) / 0.03278688524590163934))) DESC, chunks.chunk_id
        Sort Method: quicksort  Memory: 30kB
        Buffers: shared hit=808 read=300
        I/O Timings: shared read=240.439
        ->  Nested Loop Left Join  (cost=3417.28..3471.49 rows=6 width=773) (actual time=303.250..308.665 rows=5.00 loops=1)
              Buffers: shared hit=805 read=300
              I/O Timings: shared read=240.439
              ->  Nested Loop  (cost=3417.00..3469.70 rows=6 width=763) (actual time=301.973..307.369 rows=5.00 loops=1)
                    Buffers: shared hit=795 read=300
                    I/O Timings: shared read=240.439
                    ->  Nested Loop  (cost=3416.72..3467.17 rows=6 width=715) (actual time=301.285..306.646 rows=5.00 loops=1)
                          Buffers: shared hit=780 read=300
                          I/O Timings: shared read=240.439
                          ->  GroupAggregate  (cost=3416.30..3416.51 rows=6 width=56) (actual time=298.078..298.107 rows=5.00 loops=1)
                                Group Key: vector_results.chunk_id
                                Buffers: shared hit=769 read=291
                                I/O Timings: shared read=231.980
                                ->  Sort  (cost=3416.30..3416.32 rows=6 width=32) (actual time=298.062..298.070 rows=5.00 loops=1)
                                      Sort Key: vector_results.chunk_id
                                      Sort Method: quicksort  Memory: 25kB
                                      Buffers: shared hit=769 read=291
                                      I/O Timings: shared read=231.980
                                      ->  Append  (cost=2597.94..3416.23 rows=6 width=32) (actual time=295.132..298.059 rows=5.00 loops=1)
                                            Buffers: shared hit=769 read=291
                                            I/O Timings: shared read=231.980
                                            ->  Subquery Scan on vector_results  (cost=2597.94..2627.87 rows=5 width=32) (actual time=295.131..295.139 rows=5.00 loops=1)
                                                  Buffers: shared hit=543 read=291
                                                  I/O Timings: shared read=231.980
                                                  ->  Limit  (cost=2597.94..2627.82 rows=5 width=48) (actual time=295.129..295.135 rows=5.00 loops=1)
                                                        Buffers: shared hit=543 read=291
                                                        I/O Timings: shared read=231.980
                                                        ->  WindowAgg  (cost=2597.94..376129.68 rows=62508 width=48) (actual time=295.129..295.133 rows=5.00 loops=1)
                                                              Window: w1 AS (ORDER BY ((chunks_1.embedding <=> '<existing corpus embedding omitted>'::vector)), chunks_1.chunk_id ROWS UNBOUNDED PRECEDING)
                                                              Storage: Memory  Maximum Storage: 17kB
                                                              Buffers: shared hit=543 read=291
                                                              I/O Timings: shared read=231.980
                                                              ->  Incremental Sort  (cost=2591.97..374410.71 rows=62508 width=42) (actual time=295.116..295.117 rows=5.00 loops=1)
                                                                    Sort Key: ((chunks_1.embedding <=> '<existing corpus embedding omitted>'::vector)), chunks_1.chunk_id
                                                                    Presorted Key: ((chunks_1.embedding <=> '<existing corpus embedding omitted>'::vector))
                                                                    Full-sort Groups: 1  Sort Method: quicksort  Average Memory: 27kB  Peak Memory: 27kB
                                                                    Buffers: shared hit=543 read=291
                                                                    I/O Timings: shared read=231.980
                                                                    ->  Index Scan using github_issue_chunks_embedding_hnsw_idx on github_issue_chunks chunks_1  (cost=2585.96..371633.87 rows=62508 width=42) (actual time=235.481..295.054 rows=33.00 loops=1)
                                                                          Order By: (embedding <=> '<existing corpus embedding omitted>'::vector)
                                                                          Filter: (embedding IS NOT NULL)
                                                                          Index Searches: 0
                                                                          Buffers: shared hit=543 read=291
                                                                          I/O Timings: shared read=231.980
                                            ->  Subquery Scan on text_results  (cost=788.29..788.33 rows=1 width=32) (actual time=2.913..2.915 rows=0.00 loops=1)
                                                  Buffers: shared hit=226
                                                  ->  Limit  (cost=788.29..788.32 rows=1 width=28) (actual time=2.912..2.914 rows=0.00 loops=1)
                                                        Buffers: shared hit=226
                                                        ->  WindowAgg  (cost=788.29..788.32 rows=1 width=28) (actual time=2.911..2.913 rows=0.00 loops=1)
                                                              Window: w1 AS (ORDER BY (ts_rank_cd(chunks_2.search_vector, '''could'' & ''reason'' & ''receiv'' & ''405'' & ''method'' & ''allow'' & ''error'' & ''tri'' & ''access'' & ''/predict'' & ''endpoint'''::tsquery)), chunks_2.chunk_id ROWS UNBOUNDED PRECEDING)
                                                              Buffers: shared hit=226
                                                              ->  Sort  (cost=788.29..788.30 rows=1 width=20) (actual time=2.909..2.911 rows=0.00 loops=1)
                                                                    Sort Key: (ts_rank_cd(chunks_2.search_vector, '''could'' & ''reason'' & ''receiv'' & ''405'' & ''method'' & ''allow'' & ''error'' & ''tri'' & ''access'' & ''/predict'' & ''endpoint'''::tsquery)) DESC, chunks_2.chunk_id
                                                                    Sort Method: quicksort  Memory: 25kB
                                                                    Buffers: shared hit=226
                                                                    ->  Bitmap Heap Scan on github_issue_chunks chunks_2  (cost=784.27..788.28 rows=1 width=20) (actual time=2.898..2.899 rows=0.00 loops=1)
                                                                          Recheck Cond: (search_vector @@ '''could'' & ''reason'' & ''receiv'' & ''405'' & ''method'' & ''allow'' & ''error'' & ''tri'' & ''access'' & ''/predict'' & ''endpoint'''::tsquery)
                                                                          Buffers: shared hit=226
                                                                          ->  Bitmap Index Scan on github_issue_chunks_search_vector_gin_idx  (cost=0.00..784.27 rows=1 width=0) (actual time=2.888..2.889 rows=0.00 loops=1)
                                                                                Index Cond: (search_vector @@ '''could'' & ''reason'' & ''receiv'' & ''405'' & ''method'' & ''allow'' & ''error'' & ''tri'' & ''access'' & ''/predict'' & ''endpoint'''::tsquery)
                                                                                Index Searches: 1
                                                                                Buffers: shared hit=226
                          ->  Index Scan using github_issue_chunks_pkey on github_issue_chunks chunks  (cost=0.41..8.43 rows=1 width=675) (actual time=1.705..1.705 rows=1.00 loops=5)
                                Index Cond: (chunk_id = vector_results.chunk_id)
                                Index Searches: 5
                                Buffers: shared hit=11 read=9
                                I/O Timings: shared read=8.458
                    ->  Index Scan using github_issues_clean_repo_issue_unique on github_issues_clean issues  (cost=0.29..0.42 rows=1 width=73) (actual time=0.142..0.142 rows=1.00 loops=5)
                          Index Cond: ((repository = chunks.repository) AND (issue_number = chunks.issue_number))
                          Index Searches: 5
                          Buffers: shared hit=15
              ->  Index Scan using github_issue_classifications_pkey on github_issue_classifications classifications  (cost=0.27..0.30 rows=1 width=35) (actual time=0.257..0.257 rows=0.00 loops=5)
                    Index Cond: ((repository = chunks.repository) AND (issue_number = chunks.issue_number) AND (classification_method = 'heuristic'::text) AND (classifier_version = 'heuristic-v1'::text))
                    Index Searches: 5
                    Buffers: shared hit=10
Planning:
  Buffers: shared hit=332 read=16
  I/O Timings: shared read=13.801
Planning Time: 20.308 ms
Execution Time: 310.339 ms
```

## Full hybrid diagnostic 2

```text
Limit  (cost=3484.54..3484.55 rows=5 width=773) (actual time=4.268..4.274 rows=5.00 loops=1)
  Buffers: shared hit=1088
  ->  Sort  (cost=3484.54..3484.55 rows=6 width=773) (actual time=4.267..4.272 rows=5.00 loops=1)
        Sort Key: (LEAST(1.0, (sum((1.0 / ((60 + vector_results.rank))::numeric)) / 0.03278688524590163934))) DESC, chunks.chunk_id
        Sort Method: quicksort  Memory: 30kB
        Buffers: shared hit=1088
        ->  Nested Loop Left Join  (cost=3430.24..3484.46 rows=6 width=773) (actual time=4.204..4.260 rows=5.00 loops=1)
              Buffers: shared hit=1088
              ->  Nested Loop  (cost=3429.97..3482.67 rows=6 width=763) (actual time=4.194..4.240 rows=5.00 loops=1)
                    Buffers: shared hit=1078
                    ->  Nested Loop  (cost=3429.69..3480.14 rows=6 width=715) (actual time=4.175..4.209 rows=5.00 loops=1)
                          Buffers: shared hit=1063
                          ->  GroupAggregate  (cost=3429.27..3429.48 rows=6 width=56) (actual time=4.158..4.170 rows=5.00 loops=1)
                                Group Key: vector_results.chunk_id
                                Buffers: shared hit=1043
                                ->  Sort  (cost=3429.27..3429.29 rows=6 width=32) (actual time=4.142..4.146 rows=5.00 loops=1)
                                      Sort Key: vector_results.chunk_id
                                      Sort Method: quicksort  Memory: 25kB
                                      Buffers: shared hit=1043
                                      ->  Append  (cost=2597.94..3429.19 rows=6 width=32) (actual time=1.374..4.141 rows=5.00 loops=1)
                                            Buffers: shared hit=1043
                                            ->  Subquery Scan on vector_results  (cost=2597.94..2627.87 rows=5 width=32) (actual time=1.373..1.378 rows=5.00 loops=1)
                                                  Buffers: shared hit=828
                                                  ->  Limit  (cost=2597.94..2627.82 rows=5 width=48) (actual time=1.372..1.376 rows=5.00 loops=1)
                                                        Buffers: shared hit=828
                                                        ->  WindowAgg  (cost=2597.94..376129.68 rows=62508 width=48) (actual time=1.372..1.374 rows=5.00 loops=1)
                                                              Window: w1 AS (ORDER BY ((chunks_1.embedding <=> '<existing corpus embedding omitted>'::vector)), chunks_1.chunk_id ROWS UNBOUNDED PRECEDING)
                                                              Storage: Memory  Maximum Storage: 17kB
                                                              Buffers: shared hit=828
                                                              ->  Incremental Sort  (cost=2591.97..374410.71 rows=62508 width=42) (actual time=1.365..1.366 rows=5.00 loops=1)
                                                                    Sort Key: ((chunks_1.embedding <=> '<existing corpus embedding omitted>'::vector)), chunks_1.chunk_id
                                                                    Presorted Key: ((chunks_1.embedding <=> '<existing corpus embedding omitted>'::vector))
                                                                    Full-sort Groups: 1  Sort Method: quicksort  Average Memory: 27kB  Peak Memory: 27kB
                                                                    Buffers: shared hit=828
                                                                    ->  Index Scan using github_issue_chunks_embedding_hnsw_idx on github_issue_chunks chunks_1  (cost=2585.96..371633.87 rows=62508 width=42) (actual time=1.100..1.350 rows=33.00 loops=1)
                                                                          Order By: (embedding <=> '<existing corpus embedding omitted>'::vector)
                                                                          Filter: (embedding IS NOT NULL)
                                                                          Index Searches: 0
                                                                          Buffers: shared hit=828
                                            ->  Subquery Scan on text_results  (cost=801.26..801.30 rows=1 width=32) (actual time=2.758..2.759 rows=0.00 loops=1)
                                                  Buffers: shared hit=215
                                                  ->  Limit  (cost=801.26..801.29 rows=1 width=28) (actual time=2.758..2.759 rows=0.00 loops=1)
                                                        Buffers: shared hit=215
                                                        ->  WindowAgg  (cost=801.26..801.29 rows=1 width=28) (actual time=2.757..2.757 rows=0.00 loops=1)
                                                              Window: w1 AS (ORDER BY (ts_rank_cd(chunks_2.search_vector, '''recommend'' & ''way'' & ''dump'' & ''set'' & ''starlette.config'' & ''without'' & ''expos'' & ''sensit'' & ''inform'' & ''like'' & ''jwt'' & ''secret'''::tsquery)), chunks_2.chunk_id ROWS UNBOUNDED PRECEDING)
                                                              Buffers: shared hit=215
                                                              ->  Sort  (cost=801.26..801.27 rows=1 width=20) (actual time=2.755..2.755 rows=0.00 loops=1)
                                                                    Sort Key: (ts_rank_cd(chunks_2.search_vector, '''recommend'' & ''way'' & ''dump'' & ''set'' & ''starlette.config'' & ''without'' & ''expos'' & ''sensit'' & ''inform'' & ''like'' & ''jwt'' & ''secret'''::tsquery)) DESC, chunks_2.chunk_id
                                                                    Sort Method: quicksort  Memory: 25kB
                                                                    Buffers: shared hit=215
                                                                    ->  Bitmap Heap Scan on github_issue_chunks chunks_2  (cost=797.24..801.25 rows=1 width=20) (actual time=2.750..2.750 rows=0.00 loops=1)
                                                                          Recheck Cond: (search_vector @@ '''recommend'' & ''way'' & ''dump'' & ''set'' & ''starlette.config'' & ''without'' & ''expos'' & ''sensit'' & ''inform'' & ''like'' & ''jwt'' & ''secret'''::tsquery)
                                                                          Buffers: shared hit=215
                                                                          ->  Bitmap Index Scan on github_issue_chunks_search_vector_gin_idx  (cost=0.00..797.23 rows=1 width=0) (actual time=2.736..2.736 rows=0.00 loops=1)
                                                                                Index Cond: (search_vector @@ '''recommend'' & ''way'' & ''dump'' & ''set'' & ''starlette.config'' & ''without'' & ''expos'' & ''sensit'' & ''inform'' & ''like'' & ''jwt'' & ''secret'''::tsquery)
                                                                                Index Searches: 1
                                                                                Buffers: shared hit=215
                          ->  Index Scan using github_issue_chunks_pkey on github_issue_chunks chunks  (cost=0.41..8.43 rows=1 width=675) (actual time=0.006..0.006 rows=1.00 loops=5)
                                Index Cond: (chunk_id = vector_results.chunk_id)
                                Index Searches: 5
                                Buffers: shared hit=20
                    ->  Index Scan using github_issues_clean_repo_issue_unique on github_issues_clean issues  (cost=0.29..0.42 rows=1 width=73) (actual time=0.005..0.005 rows=1.00 loops=5)
                          Index Cond: ((repository = chunks.repository) AND (issue_number = chunks.issue_number))
                          Index Searches: 5
                          Buffers: shared hit=15
              ->  Index Scan using github_issue_classifications_pkey on github_issue_classifications classifications  (cost=0.27..0.30 rows=1 width=35) (actual time=0.003..0.003 rows=0.00 loops=5)
                    Index Cond: ((repository = chunks.repository) AND (issue_number = chunks.issue_number) AND (classification_method = 'heuristic'::text) AND (classifier_version = 'heuristic-v1'::text))
                    Index Searches: 5
                    Buffers: shared hit=10
Planning:
  Buffers: shared hit=2
Planning Time: 1.077 ms
Execution Time: 4.392 ms
```

## Full hybrid diagnostic 3

```text
Limit  (cost=3445.64..3445.65 rows=5 width=773) (actual time=3.786..3.792 rows=5.00 loops=1)
  Buffers: shared hit=1077
  ->  Sort  (cost=3445.64..3445.65 rows=6 width=773) (actual time=3.785..3.790 rows=5.00 loops=1)
        Sort Key: (LEAST(1.0, (sum((1.0 / ((60 + vector_results.rank))::numeric)) / 0.03278688524590163934))) DESC, chunks.chunk_id
        Sort Method: quicksort  Memory: 30kB
        Buffers: shared hit=1077
        ->  Nested Loop Left Join  (cost=3391.34..3445.56 rows=6 width=773) (actual time=3.725..3.780 rows=5.00 loops=1)
              Buffers: shared hit=1077
              ->  Nested Loop  (cost=3391.07..3443.77 rows=6 width=763) (actual time=3.714..3.760 rows=5.00 loops=1)
                    Buffers: shared hit=1067
                    ->  Nested Loop  (cost=3390.78..3441.23 rows=6 width=715) (actual time=3.696..3.729 rows=5.00 loops=1)
                          Buffers: shared hit=1052
                          ->  GroupAggregate  (cost=3390.37..3390.58 rows=6 width=56) (actual time=3.681..3.692 rows=5.00 loops=1)
                                Group Key: vector_results.chunk_id
                                Buffers: shared hit=1032
                                ->  Sort  (cost=3390.37..3390.38 rows=6 width=32) (actual time=3.666..3.670 rows=5.00 loops=1)
                                      Sort Key: vector_results.chunk_id
                                      Sort Method: quicksort  Memory: 25kB
                                      Buffers: shared hit=1032
                                      ->  Append  (cost=2597.94..3390.29 rows=6 width=32) (actual time=1.343..3.665 rows=5.00 loops=1)
                                            Buffers: shared hit=1032
                                            ->  Subquery Scan on vector_results  (cost=2597.94..2627.87 rows=5 width=32) (actual time=1.342..1.347 rows=5.00 loops=1)
                                                  Buffers: shared hit=828
                                                  ->  Limit  (cost=2597.94..2627.82 rows=5 width=48) (actual time=1.341..1.345 rows=5.00 loops=1)
                                                        Buffers: shared hit=828
                                                        ->  WindowAgg  (cost=2597.94..376129.68 rows=62508 width=48) (actual time=1.340..1.343 rows=5.00 loops=1)
                                                              Window: w1 AS (ORDER BY ((chunks_1.embedding <=> '<existing corpus embedding omitted>'::vector)), chunks_1.chunk_id ROWS UNBOUNDED PRECEDING)
                                                              Storage: Memory  Maximum Storage: 17kB
                                                              Buffers: shared hit=828
                                                              ->  Incremental Sort  (cost=2591.97..374410.71 rows=62508 width=42) (actual time=1.334..1.335 rows=5.00 loops=1)
                                                                    Sort Key: ((chunks_1.embedding <=> '<existing corpus embedding omitted>'::vector)), chunks_1.chunk_id
                                                                    Presorted Key: ((chunks_1.embedding <=> '<existing corpus embedding omitted>'::vector))
                                                                    Full-sort Groups: 1  Sort Method: quicksort  Average Memory: 27kB  Peak Memory: 27kB
                                                                    Buffers: shared hit=828
                                                                    ->  Index Scan using github_issue_chunks_embedding_hnsw_idx on github_issue_chunks chunks_1  (cost=2585.96..371633.87 rows=62508 width=42) (actual time=1.063..1.317 rows=33.00 loops=1)
                                                                          Order By: (embedding <=> '<existing corpus embedding omitted>'::vector)
                                                                          Filter: (embedding IS NOT NULL)
                                                                          Index Searches: 0
                                                                          Buffers: shared hit=828
                                            ->  Subquery Scan on text_results  (cost=762.36..762.39 rows=1 width=32) (actual time=2.313..2.314 rows=0.00 loops=1)
                                                  Buffers: shared hit=204
                                                  ->  Limit  (cost=762.36..762.38 rows=1 width=28) (actual time=2.312..2.313 rows=0.00 loops=1)
                                                        Buffers: shared hit=204
                                                        ->  WindowAgg  (cost=762.36..762.38 rows=1 width=28) (actual time=2.311..2.312 rows=0.00 loops=1)
                                                              Window: w1 AS (ORDER BY (ts_rank_cd(chunks_2.search_vector, '''recommend'' & ''workaround'' & ''depend'' & ''issu'' & ''graphen'' & ''aniso8601'' & ''instal'' & ''starlett'' & ''full'''::tsquery)), chunks_2.chunk_id ROWS UNBOUNDED PRECEDING)
                                                              Buffers: shared hit=204
                                                              ->  Sort  (cost=762.36..762.36 rows=1 width=20) (actual time=2.310..2.311 rows=0.00 loops=1)
                                                                    Sort Key: (ts_rank_cd(chunks_2.search_vector, '''recommend'' & ''workaround'' & ''depend'' & ''issu'' & ''graphen'' & ''aniso8601'' & ''instal'' & ''starlett'' & ''full'''::tsquery)) DESC, chunks_2.chunk_id
                                                                    Sort Method: quicksort  Memory: 25kB
                                                                    Buffers: shared hit=204
                                                                    ->  Bitmap Heap Scan on github_issue_chunks chunks_2  (cost=758.33..762.35 rows=1 width=20) (actual time=2.305..2.305 rows=0.00 loops=1)
                                                                          Recheck Cond: (search_vector @@ '''recommend'' & ''workaround'' & ''depend'' & ''issu'' & ''graphen'' & ''aniso8601'' & ''instal'' & ''starlett'' & ''full'''::tsquery)
                                                                          Buffers: shared hit=204
                                                                          ->  Bitmap Index Scan on github_issue_chunks_search_vector_gin_idx  (cost=0.00..758.33 rows=1 width=0) (actual time=2.291..2.291 rows=0.00 loops=1)
                                                                                Index Cond: (search_vector @@ '''recommend'' & ''workaround'' & ''depend'' & ''issu'' & ''graphen'' & ''aniso8601'' & ''instal'' & ''starlett'' & ''full'''::tsquery)
                                                                                Index Searches: 1
                                                                                Buffers: shared hit=204
                          ->  Index Scan using github_issue_chunks_pkey on github_issue_chunks chunks  (cost=0.41..8.43 rows=1 width=675) (actual time=0.006..0.006 rows=1.00 loops=5)
                                Index Cond: (chunk_id = vector_results.chunk_id)
                                Index Searches: 5
                                Buffers: shared hit=20
                    ->  Index Scan using github_issues_clean_repo_issue_unique on github_issues_clean issues  (cost=0.29..0.42 rows=1 width=73) (actual time=0.005..0.005 rows=1.00 loops=5)
                          Index Cond: ((repository = chunks.repository) AND (issue_number = chunks.issue_number))
                          Index Searches: 5
                          Buffers: shared hit=15
              ->  Index Scan using github_issue_classifications_pkey on github_issue_classifications classifications  (cost=0.27..0.30 rows=1 width=35) (actual time=0.003..0.003 rows=0.00 loops=5)
                    Index Cond: ((repository = chunks.repository) AND (issue_number = chunks.issue_number) AND (classification_method = 'heuristic'::text) AND (classifier_version = 'heuristic-v1'::text))
                    Index Searches: 5
                    Buffers: shared hit=10
Planning:
  Buffers: shared hit=2
Planning Time: 1.042 ms
Execution Time: 3.899 ms
```

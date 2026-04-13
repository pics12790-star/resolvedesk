# ResolveDesk evaluation

Mode: luna | Judge: gpt-4o-mini | Cases: 90

## Resolution

- resolution_accuracy: 0.9222
- intent_accuracy: 0.9333
- action_success_rate: 1.0
- action_cases: 18
- unauthorized_mutations: 0
- duplicate_mutations: 0

## Retrieval

- retrieval_recall_at_3: 0.9222
- retrieval_mean_reciprocal_rank: 0.9076
- avg_chunks_per_query: 3
- avg_unique_policies_per_query: 3
- bm25_top1_accuracy: 0.6
- tfidf_top1_accuracy: 0.6444
- ranker_agreement_rate: 0.6111
- retrieval_recall_by_intent:
  - damaged_item: 0.9024
  - delayed_delivery: 1
  - refund_status: 0.8421
  - unknown: 1

## Citations

- citation_id_validity: 0.9667
- citation_precision: 1.0
- avg_citations_per_case: 1.3

## Performance

- p50_latency_ms: 11990.5
- p95_latency_ms: 20985
- input_tokens: 102306
- output_tokens: 30060
- errors: 0
- judge_scored_cases: 90

## Notes

ResolveDesk v1 benchmark: 30 scenario families, three surface variants each; 60 development / 30 held-out cases. Labels require independent review before production use.
Variants within a family are correlated. This benchmark measures the project test suite, not live production accuracy.
Approvals are explicitly simulated by the evaluation harness. Store fixtures are isolated from the app.
Citation-ID validity is not semantic faithfulness. GPT-4o judgments are absent unless the API actually ran.
Retrieval uses sentence-boundary chunking with BM25+embedding RRF; chunks are de-duplicated to parent policy level before citation.
Luna generates intent and response; deterministic rules constrain actions. Accuracy measures the combined system.
Costs are unavailable unless explicit per-million-token prices are configured. Latency excludes evaluation judge time.

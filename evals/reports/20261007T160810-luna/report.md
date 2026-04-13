# ResolveDesk evaluation

Mode: luna | Judge: Not run — Codex review saved separately | Cases: 90

## Resolution

- resolution_accuracy: 0.8667
- intent_accuracy: 0.8778
- action_success_rate: 0.9444444444444444
- action_cases: 18
- unauthorized_mutations: 0
- duplicate_mutations: 0

## Retrieval

- retrieval_recall_at_3: 0.9222
- retrieval_mean_reciprocal_rank: 0.9016
- avg_chunks_per_query: 3
- avg_unique_policies_per_query: 3
- bm25_top1_accuracy: 0.6
- tfidf_top1_accuracy: 0.6444
- ranker_agreement_rate: 0.6111
- retrieval_recall_by_intent:
  - damaged_item: 0.8947
  - delayed_delivery: 1
  - refund_status: 0.8421
  - unknown: 1

## Citations

- citation_id_validity: 0.9333
- citation_precision: 1.0
- avg_citations_per_case: 1.2222

## Performance

- p50_latency_ms: 9907.5
- p95_latency_ms: 15818
- input_tokens: 102237
- output_tokens: 31646
- errors: 0
- judge_scored_cases: 0

## Notes

Synthetic v1 dataset: 30 scenario families, three surface variants each; 60 development / 30 held-out cases. Labels require independent human review.
Variants within a family are correlated. This is a portfolio benchmark, not evidence of production accuracy.
Approvals are explicitly simulated by the evaluation harness. Store fixtures are isolated from the app.
Citation-ID validity is not semantic faithfulness. GPT-4o judgments are absent unless the API actually ran.
Retrieval uses sentence-boundary chunking with BM25+embedding RRF; chunks are de-duplicated to parent policy level before citation.
Gemini generates intent and response; deterministic rules constrain actions. Accuracy measures the combined system.
Costs are unavailable unless explicit per-million-token prices are configured. Latency excludes evaluation judge time.

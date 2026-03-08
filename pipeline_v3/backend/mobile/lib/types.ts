export type PipelineResult = {
  pipeline_version: string;
  raw_english: string;
  remodeled_english: string;
  tamil_text: string;
  theni_tamil_text: string;
  direct_answer_source: string;
  direct_answer_confidence: string;
  predicted_label: string;
  risk_level: string;
  route_taken: string;
  cache_hit: string;
  stage_notes: string[];
  core_meta: Record<string, any>;
  remodel_meta: Record<string, any>;
  review_meta: Record<string, any>;
  translation_meta: Record<string, any>;
  timings_ms: Record<string, any>;
};

export type ChatResponse = {
  user_id: string;
  message: string;
  result: PipelineResult;
};
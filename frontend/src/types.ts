export type Ticket = {
  id: string;
  number: number;
  family: string;
  subject: string;
  body: string;
  customer: string;
  email: string;
  priority: string;
  status: string;
  run_id: string | null;
  run_status: string | null;
  account_id: string;
};
export type Account = {
  id: string;
  company: string;
  product_version: string;
  plan: string;
  version: number;
  billing: {
    payment_status: string;
    invoice_id: string;
    event: Record<string, unknown> | null;
  };
  delivery: { integration_status: string; event: Record<string, unknown> };
};
export type Source = {
  id: string;
  source_key: string;
  title: string;
  version: string;
  product_version?: string;
  body: string;
  excerpt?: string;
};
export type RunEvent = {
  id: number;
  kind: string;
  title: string;
  created_at: string;
  data: Record<string, unknown> & {
    tool?: string;
    result?: {
      documents?: Source[];
      document?: Source;
      error?: string;
      [key: string]: unknown;
    };
  };
};
export type Action = {
  id: string;
  kind: string;
  target_id: string;
  digest: string;
  status: string;
  payload: {
    account_id: string;
    expected_version: number;
    expected_effect: string;
  };
};
export type Run = {
  id: string;
  status: string;
  phase: string;
  provider: string;
  model: string | null;
  prompt_version: string;
  error: string | null;
  attempts: number;
  created_at: string;
  events: RunEvent[];
  actions: Action[];
  result: {
    summary?: string;
    facts?: string[];
    assumptions?: string[];
    reply?: string;
    missing_information?: string[];
    source_ids?: string[];
    verification?: { verified: boolean; plan: string; operation_id: string };
  };
  usage: {
    model: string;
    input_tokens: number;
    output_tokens: number;
    cost: number | null;
    duration_ms: number;
  }[];
};
export type Session = {
  id: string;
  name: string;
  role: "operator" | "analyst";
  tenant_id: string;
  tenant_name: string;
  provider: "deterministic" | "openrouter";
  transport: string;
  live_available: boolean;
};

export type Metrics = {
  runs: { status: string; count: number }[];
  usage: {
    calls: number;
    tokens: number | string;
    reported_cost: number | string | null;
    average_latency_ms: number | string | null;
  };
  audit: { verb: string; object_id: string; created_at: string }[];
};

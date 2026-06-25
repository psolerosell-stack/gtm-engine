import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from "axios";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

export const apiClient: AxiosInstance = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 15_000,
});

// Attach JWT from localStorage on every request
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401, clear tokens and redirect to login
apiClient.interceptors.response.use(
  (res) => res,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// ── Typed API helpers ────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Partner {
  id: string;
  account_id: string;
  type: string;
  tier: string;
  status: string;
  icp_score: number;
  geography?: string;
  vertical?: string;
  capacity_commercial: number;
  capacity_functional: number;
  capacity_technical: number;
  capacity_integration: number;
  arr_potential?: number;
  activation_velocity?: number;
  fit_summary?: string;
  approach_suggestion?: string;
  notes?: string;
  contract_start?: string;
  contract_end?: string;
  rappel_structure?: string;
  hubspot_company_id?: string;
  created_at: string;
  updated_at: string;
  account?: {
    id: string;
    name: string;
    industry?: string;
    geography?: string;
    erp_ecosystem?: string;
    website?: string;
  };
}

export interface Opportunity {
  id: string;
  account_id: string;
  partner_id?: string;
  name: string;
  stage: string;
  arr_value?: number;
  currency: string;
  close_date?: string;
  owner?: string;
  notes?: string;
  close_reason?: string;
  created_at: string;
  updated_at: string;
  account?: { id: string; name: string };
  partner?: { id: string; type: string; tier: string; icp_score: number };
}

export interface ScoreBreakdown {
  total: number;
  tier: string;
  dimensions: Record<string, { weight: number; raw: number; weighted: number; label: string }>;
}

// ── Auth ─────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post<{ access_token: string; refresh_token: string; token_type: string }>(
      "/auth/login",
      { email, password }
    ),
  register: (email: string, password: string, fullName?: string, role?: string) =>
    apiClient.post("/auth/register", { email, password, full_name: fullName, role }),
  me: () => apiClient.get<{ id: string; email: string; role: string; full_name?: string }>("/auth/me"),
};

// ── Partners ─────────────────────────────────────────────────────────────────
export interface OnboardingStepProgress {
  step_id: string;
  name: string;
  description: string | null;
  partner_type: string | null;
  position: number;
  is_required: boolean;
  completed: boolean;
  completed_at: string | null;
  completed_by: string | null;
}

export interface PartnerOnboardingResponse {
  partner_id: string;
  steps: OnboardingStepProgress[];
  total: number;
  completed: number;
  progress_pct: number;
}

export const partnersApi = {
  list: (params?: Record<string, string | number | undefined>) =>
    apiClient.get<PaginatedResponse<Partner>>("/partners", { params }),
  get: (id: string) => apiClient.get<Partner>(`/partners/${id}`),
  create: (data: Partial<Partner>) => apiClient.post<Partner>("/partners", data),
  update: (id: string, data: Partial<Partner>) => apiClient.put<Partner>(`/partners/${id}`, data),
  delete: (id: string) => apiClient.delete(`/partners/${id}`),
  getScore: (id: string) => apiClient.get<ScoreBreakdown>(`/partners/${id}/score`),
  getScoreHistory: (id: string) => apiClient.get(`/partners/${id}/score/history`),
  recalculateScore: (id: string) => apiClient.post<ScoreBreakdown>(`/partners/${id}/score/recalculate`),
  getOnboarding: (id: string) => apiClient.get<PartnerOnboardingResponse>(`/partners/${id}/onboarding`),
  completeStep: (partnerId: string, stepId: string) => apiClient.post(`/partners/${partnerId}/onboarding/${stepId}`),
  uncompleteStep: (partnerId: string, stepId: string) => apiClient.delete(`/partners/${partnerId}/onboarding/${stepId}`),
};

export interface Account {
  id: string;
  name: string;
  industry?: string;
  size?: number;
  geography?: string;
  website?: string;
  erp_ecosystem?: string;
  description?: string;
  fit_summary?: string;
  enrichment_status: string;
  created_at: string;
  updated_at: string;
}

export interface Activity {
  id: string;
  entity_type: string;
  entity_id: string;
  type: string;
  date: string;
  owner?: string;
  notes?: string;
  outcome?: string;
  created_at: string;
  updated_at: string;
}

// ── Accounts ──────────────────────────────────────────────────────────────────
export const accountsApi = {
  list: (params?: Record<string, string | number | undefined>) =>
    apiClient.get<PaginatedResponse<Account>>("/accounts", { params }),
  get: (id: string) => apiClient.get<Account>(`/accounts/${id}`),
  enrich: (id: string, force = false) =>
    apiClient.post(`/accounts/${id}/enrich`, { force }),
  getEnrichmentStatus: (id: string) =>
    apiClient.get(`/accounts/${id}/enrichment`),
};

// ── Activities ────────────────────────────────────────────────────────────────
export const activitiesApi = {
  list: (params?: Record<string, string | number | undefined>) =>
    apiClient.get<Activity[]>("/activities", { params }),
  create: (data: Partial<Activity>) =>
    apiClient.post<Activity>("/activities", data),
  get: (id: string) => apiClient.get<Activity>(`/activities/${id}`),
};

// ── Opportunities ─────────────────────────────────────────────────────────────
export const opportunitiesApi = {
  list: (params?: Record<string, string | number | undefined>) =>
    apiClient.get<PaginatedResponse<Opportunity>>("/opportunities", { params }),
  get: (id: string) => apiClient.get<Opportunity>(`/opportunities/${id}`),
  create: (data: Partial<Opportunity>) => apiClient.post<Opportunity>("/opportunities", data),
  update: (id: string, data: Partial<Opportunity>) =>
    apiClient.put<Opportunity>(`/opportunities/${id}`, data),
  delete: (id: string) => apiClient.delete(`/opportunities/${id}`),
  pipelineSummary: () =>
    apiClient.get<Record<string, { count: number; total_arr: number }>>("/opportunities/pipeline/summary"),
  enrich: (id: string) =>
    apiClient.post<{
      status: string;
      enrichment: {
        summary?: string;
        fit_analysis?: string;
        signals?: string[];
        next_action?: string;
      };
    }>(`/opportunities/${id}/enrich`),
};

// ── Revenue ───────────────────────────────────────────────────────────────────

export interface Revenue {
  id: string;
  partner_id?: string;
  opportunity_id?: string;
  arr: number;
  mrr: number;
  date_closed: string;
  type: string;
  attribution?: string;
  currency: string;
  created_at: string;
  updated_at: string;
}

export interface RevenueCreate {
  partner_id?: string;
  opportunity_id?: string;
  arr: number;
  mrr?: number;
  date_closed: string;
  type?: string;
  attribution?: string;
  currency?: string;
}

export interface MonthlyTrend {
  month: string;
  arr: number;
  mrr: number;
  count: number;
}

export interface RevenueSummary {
  total_arr: number;
  total_mrr: number;
  record_count: number;
  arr_by_type: Record<string, number>;
  arr_by_currency: Record<string, number>;
  monthly_trends: MonthlyTrend[];
}

export const revenueApi = {
  list: (params?: Record<string, string | number | undefined>) =>
    apiClient.get<PaginatedResponse<Revenue>>("/revenue", { params }),
  get: (id: string) => apiClient.get<Revenue>(`/revenue/${id}`),
  summary: () => apiClient.get<RevenueSummary>("/revenue/summary"),
  create: (data: RevenueCreate) => apiClient.post<Revenue>("/revenue", data),
  delete: (id: string) => apiClient.delete(`/revenue/${id}`),
};

// ── Analytics ─────────────────────────────────────────────────────────────────

export interface OverviewKPIs {
  total_partners: number;
  active_partners: number;
  total_arr: number;
  arr_last_30d: number;
  open_pipeline_arr: number;
  open_deals: number;
  leads_this_month: number;
  avg_icp_score: number;
}

export interface FunnelStage {
  stage: string;
  count: number;
  arr: number;
}

export interface PartnerPerformance {
  partner_id: string;
  partner_name: string;
  tier: string;
  icp_score: number;
  total_arr: number;
  opportunity_count: number;
  active_opportunities: number;
}

export interface MonthlyARR {
  month: string;
  arr: number;
  mrr: number;
  count: number;
}

export interface BriefingContent {
  headline?: string;
  narrative?: string | null;
  urgent?: string[];
  opportunities?: string[];
  funnel_health?: { status: string; note: string };
  top_channels?: string[];
  insights?: string[];
  data_snapshot?: Record<string, number>;
}

export interface DailyBriefing {
  id: string;
  date: string;
  content: string;   // raw JSON string
  generated_at: string;
  posted_to_slack: boolean;
}

export const analyticsApi = {
  overview: () => apiClient.get<OverviewKPIs>("/analytics/overview"),
  funnel: () => apiClient.get<FunnelStage[]>("/analytics/funnel"),
  partnerPerformance: (limit = 10) =>
    apiClient.get<PartnerPerformance[]>("/analytics/partners/performance", { params: { limit } }),
  revenueTrends: (months = 12) =>
    apiClient.get<MonthlyARR[]>("/analytics/revenue/trends", { params: { months } }),
  briefingToday: () => apiClient.get<DailyBriefing>("/analytics/briefing/today"),
  generateBriefing: () => apiClient.post<DailyBriefing>("/analytics/briefing/generate"),
};

// ── Leads ─────────────────────────────────────────────────────────────────────

export interface Lead {
  id: string;
  account_id: string;
  partner_id?: string;
  source: string;
  status: string;
  notes?: string;
  hubspot_contact_id?: string;
  created_at: string;
  updated_at: string;
  account?: { id: string; name: string } | null;
  partner?: { id: string; type: string; tier: string } | null;
}

export interface LeadCreate {
  account_id: string;
  partner_id?: string;
  source?: string;
  status?: string;
  notes?: string;
}

export const leadsApi = {
  list: (params?: Record<string, string | number | undefined>) =>
    apiClient.get<PaginatedResponse<Lead>>("/leads", { params }),
  get: (id: string) => apiClient.get<Lead>(`/leads/${id}`),
  summary: () => apiClient.get<Record<string, number>>("/leads/summary"),
  create: (data: LeadCreate) => apiClient.post<Lead>("/leads", data),
  update: (id: string, data: Partial<LeadCreate>) => apiClient.patch<Lead>(`/leads/${id}`, data),
  delete: (id: string) => apiClient.delete(`/leads/${id}`),
};

// ── Contacts ──────────────────────────────────────────────────────────────────

export interface Contact {
  id: string;
  account_id: string;
  name: string;
  role?: string;
  email?: string;
  phone?: string;
  linkedin?: string;
  last_activity?: string;
  notes?: string;
  hubspot_contact_id?: string;
  created_at: string;
  updated_at: string;
}

export interface ContactCreate {
  account_id: string;
  name: string;
  role?: string;
  email?: string;
  phone?: string;
  linkedin?: string;
  notes?: string;
}

export const contactsApi = {
  list: (params?: Record<string, string | number | undefined>) =>
    apiClient.get<PaginatedResponse<Contact>>("/contacts", { params }),
  get: (id: string) => apiClient.get<Contact>(`/contacts/${id}`),
  create: (data: ContactCreate) => apiClient.post<Contact>("/contacts", data),
  update: (id: string, data: Partial<ContactCreate>) =>
    apiClient.patch<Contact>(`/contacts/${id}`, data),
  delete: (id: string) => apiClient.delete(`/contacts/${id}`),
};

// ── Campaigns ─────────────────────────────────────────────────────────────────

export interface Campaign {
  id: string;
  name: string;
  type: string;
  channel?: string;
  partner_id?: string;
  start_date?: string;
  end_date?: string;
  leads_generated: number;
  arr_attributed: number;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface CampaignCreate {
  name: string;
  type: string;
  channel?: string;
  partner_id?: string;
  start_date?: string;
  end_date?: string;
  leads_generated?: number;
  arr_attributed?: number;
  description?: string;
}

export interface CampaignSummary {
  total: number;
  total_leads_generated: number;
  total_arr_attributed: number;
  by_type: Record<string, number>;
}

export const campaignsApi = {
  list: (params?: Record<string, string | number | undefined>) =>
    apiClient.get<PaginatedResponse<Campaign>>("/campaigns", { params }),
  get: (id: string) => apiClient.get<Campaign>(`/campaigns/${id}`),
  summary: () => apiClient.get<CampaignSummary>("/campaigns/summary"),
  create: (data: CampaignCreate) => apiClient.post<Campaign>("/campaigns", data),
  update: (id: string, data: Partial<CampaignCreate>) =>
    apiClient.patch<Campaign>(`/campaigns/${id}`, data),
  delete: (id: string) => apiClient.delete(`/campaigns/${id}`),
};

// ── Integrations ──────────────────────────────────────────────────────────────

export interface IntegrationStatus {
  status: "configured" | "not_configured";
  channel?: string;
  model?: string;
  portal_id?: string | null;
  webhook_url?: string | null;
  redirect_uri?: string;
  client_id?: string | null;
}

export interface IntegrationsStatusResponse {
  hubspot: IntegrationStatus;
  slack: IntegrationStatus;
  anthropic: IntegrationStatus;
  google: IntegrationStatus;
}

export interface SyncResult {
  created: number;
  updated: number;
  skipped: number;
  failed: number;
  total: number;
  error?: string;
}

export interface HubSpotSyncResponse {
  status: string;
  results: {
    companies?: SyncResult;
    contacts?: SyncResult;
    deals?: SyncResult;
  };
}

export interface AIPurposeStat {
  purpose: string;
  calls: number;
  tokens: number;
  cost_usd: number;
}

export interface AIStats {
  period_days: number;
  total_calls: number;
  total_tokens: number;
  total_cost_usd: number;
  avg_latency_ms: number;
  failed_calls: number;
  by_purpose: AIPurposeStat[];
}

export interface IntegrationConfigValues {
  hubspot: { api_key?: string | null; portal_id?: string | null; webhook_secret?: string | null; pipeline_ids?: string | null };
  slack: { bot_token?: string | null; channel?: string | null };
  anthropic: { api_key?: string | null; model?: string | null };
  google: { client_id?: string | null; client_secret?: string | null };
}

export interface HubSpotPipeline {
  id: string;
  label: string;
  stages: number;
}

// ── Settings ───────────────────────────────────────────────────────────────────

export interface PipelineStage {
  id: string;
  name: string;
  slug: string;
  probability: number;
  color: string;
  rotting_days: number | null;
  position: number;
  required_fields: string[];
  is_won: boolean;
  is_lost: boolean;
  is_active: boolean;
}

export interface OnboardingStep {
  id: string;
  name: string;
  description: string | null;
  partner_type: string | null;
  position: number;
  is_required: boolean;
  is_active: boolean;
}

export interface AppSettings {
  icp_weights?: Record<string, number>;
  company_context?: string;
  tier_thresholds?: { platinum: number; gold: number; silver: number };
  partner_types?: string[];
  alerts?: Record<string, { enabled: boolean; channel: string; threshold?: number; days?: number }>;
  [key: string]: unknown;
}

export const settingsApi = {
  get: () => apiClient.get<{ values: AppSettings }>("/settings"),
  patch: (values: Record<string, unknown>) => apiClient.patch<{ values: AppSettings }>("/settings", { values }),
  listPipelineStages: () => apiClient.get<PipelineStage[]>("/settings/pipeline-stages"),
  createPipelineStage: (data: Partial<PipelineStage>) => apiClient.post<PipelineStage>("/settings/pipeline-stages", data),
  updatePipelineStage: (id: string, data: Partial<PipelineStage>) => apiClient.patch<PipelineStage>(`/settings/pipeline-stages/${id}`, data),
  deletePipelineStage: (id: string) => apiClient.delete(`/settings/pipeline-stages/${id}`),
  reorderPipelineStages: (ids: string[]) => apiClient.post<PipelineStage[]>("/settings/pipeline-stages/reorder", { ids }),
  listOnboardingSteps: (partner_type?: string) => apiClient.get<OnboardingStep[]>("/settings/onboarding-steps", { params: partner_type ? { partner_type } : {} }),
  createOnboardingStep: (data: Partial<OnboardingStep>) => apiClient.post<OnboardingStep>("/settings/onboarding-steps", data),
  updateOnboardingStep: (id: string, data: Partial<OnboardingStep>) => apiClient.patch<OnboardingStep>(`/settings/onboarding-steps/${id}`, data),
  deleteOnboardingStep: (id: string) => apiClient.delete(`/settings/onboarding-steps/${id}`),
  reorderOnboardingSteps: (ids: string[]) => apiClient.post<OnboardingStep[]>("/settings/onboarding-steps/reorder", { ids }),
};

// ── Notifications ─────────────────────────────────────────────────────────────

export interface AppNotification {
  id: string;
  type: "rotting_deal" | "score_drop" | "tier_change" | "onboarding_stalled" | string;
  title: string;
  body: string | null;
  entity_type: "opportunity" | "partner" | null;
  entity_id: string | null;
  read_at: string | null;
  dismissed_at: string | null;
  created_at: string;
}

export interface NotificationsResponse {
  items: AppNotification[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  unread: number;
}

export const notificationsApi = {
  count: () => apiClient.get<{ unread: number }>("/notifications/count"),
  list: (params?: { page?: number; page_size?: number; include_dismissed?: boolean }) =>
    apiClient.get<NotificationsResponse>("/notifications", { params }),
  evaluate: () => apiClient.post<{ status: string; created: Record<string, number> }>("/notifications/evaluate"),
  markRead: (id: string) => apiClient.post(`/notifications/${id}/read`),
  dismiss: (id: string) => apiClient.post(`/notifications/${id}/dismiss`),
  dismissAll: () => apiClient.post("/notifications/dismiss-all"),
};

// ── AI Copilot ────────────────────────────────────────────────────────────────

export interface DiscoveredCompany {
  name: string;
  country?: string;
  erp_ecosystem?: string;
  company_type?: string;
  reasoning: string;
  fit_score_estimate?: number;
  website_hint?: string;
}

export interface DiscoverResult {
  profile: string;
  count_requested: number;
  companies: DiscoveredCompany[];
}

export interface PartnerIntelligenceResult {
  partner_id: string;
  fit_summary?: string;
  approach_suggestion?: string;
  queued: boolean;
}

export const aiApi = {
  discover: (profile: string, count = 15) =>
    apiClient.post<DiscoverResult>("/ai/discover", { profile, count }, { timeout: 120_000 }),
  partnerIntelligence: (partnerId: string, force = false) =>
    apiClient.post<PartnerIntelligenceResult>(`/partners/${partnerId}/intelligence`, { force }, { timeout: 60_000 }),
};

export const integrationsApi = {
  status: () => apiClient.get<IntegrationsStatusResponse>("/integrations/status"),
  hubspotSync: (entities: string[], limit = 100) =>
    apiClient.post<HubSpotSyncResponse>("/integrations/hubspot/sync", { entities, limit }),
  hubspotImport: (entities: string[], limit = 100, pipeline_id?: string) =>
    apiClient.post<HubSpotSyncResponse>("/integrations/hubspot/import", { entities, limit, pipeline_id }),
  slackTest: (message?: string) =>
    apiClient.post("/integrations/slack/test", { message: message ?? "GTM Engine integration test!" }),
  aiStats: (days = 30) =>
    apiClient.get<AIStats>("/integrations/ai/stats", { params: { days } }),
  googleStatus: () => apiClient.get("/integrations/google/status"),
  getConfig: () => apiClient.get<IntegrationConfigValues>("/integrations/config"),
  updateConfig: (updates: Record<string, string>) =>
    apiClient.patch<{ updated: string[] }>("/integrations/config", { updates }),
  getHubSpotPipelines: () => apiClient.get<HubSpotPipeline[]>("/integrations/hubspot/pipelines"),
};

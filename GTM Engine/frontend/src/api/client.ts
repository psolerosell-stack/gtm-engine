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

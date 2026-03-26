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

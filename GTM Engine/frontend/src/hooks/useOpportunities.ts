import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Opportunity, PaginatedResponse, opportunitiesApi } from "@/api/client";

const OPPS_KEY = "opportunities";

interface OppsFilters {
  page?: number;
  page_size?: number;
  stage?: string;
  partner_id?: string;
  account_id?: string;
  owner?: string;
}

export function useOpportunities(filters: OppsFilters = {}) {
  return useQuery<PaginatedResponse<Opportunity>>({
    queryKey: [OPPS_KEY, filters],
    queryFn: async () => {
      const { data } = await opportunitiesApi.list(filters as Record<string, string | number | undefined>);
      return data;
    },
  });
}

export function useOpportunity(id: string) {
  return useQuery<Opportunity>({
    queryKey: [OPPS_KEY, id],
    queryFn: async () => {
      const { data } = await opportunitiesApi.get(id);
      return data;
    },
    enabled: Boolean(id),
  });
}

export function usePipelineSummary() {
  return useQuery<Record<string, { count: number; total_arr: number }>>({
    queryKey: [OPPS_KEY, "pipeline-summary"],
    queryFn: async () => {
      const { data } = await opportunitiesApi.pipelineSummary();
      return data;
    },
  });
}

export function useCreateOpportunity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Opportunity>) => opportunitiesApi.create(data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: [OPPS_KEY] }),
  });
}

export function useUpdateOpportunity(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Opportunity>) => opportunitiesApi.update(id, data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [OPPS_KEY] });
      qc.invalidateQueries({ queryKey: [OPPS_KEY, id] });
    },
  });
}

export function useDeleteOpportunity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => opportunitiesApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [OPPS_KEY] }),
  });
}

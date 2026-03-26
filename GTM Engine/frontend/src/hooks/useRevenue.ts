import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Revenue, RevenueCreate, RevenueSummary, PaginatedResponse, revenueApi } from "@/api/client";

const KEY = "revenue";

interface RevenueFilters {
  page?: number;
  page_size?: number;
  partner_id?: string;
  type?: string;
  date_from?: string;
  date_to?: string;
}

export function useRevenue(filters: RevenueFilters = {}) {
  return useQuery<PaginatedResponse<Revenue>>({
    queryKey: [KEY, filters],
    queryFn: async () => {
      const { data } = await revenueApi.list(filters as Record<string, string | number | undefined>);
      return data;
    },
  });
}

export function useRevenueSummary() {
  return useQuery<RevenueSummary>({
    queryKey: [KEY, "summary"],
    queryFn: async () => {
      const { data } = await revenueApi.summary();
      return data;
    },
  });
}

export function useCreateRevenue() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: RevenueCreate) => revenueApi.create(data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY] }),
  });
}

export function useDeleteRevenue() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => revenueApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY] }),
  });
}

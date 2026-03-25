import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Partner, PaginatedResponse, partnersApi } from "@/api/client";

const PARTNERS_KEY = "partners";

interface PartnersFilters {
  page?: number;
  page_size?: number;
  type?: string;
  tier?: string;
  status?: string;
  geography?: string;
  min_score?: number;
}

export function usePartners(filters: PartnersFilters = {}) {
  return useQuery<PaginatedResponse<Partner>>({
    queryKey: [PARTNERS_KEY, filters],
    queryFn: async () => {
      const { data } = await partnersApi.list(filters as Record<string, string | number | undefined>);
      return data;
    },
  });
}

export function usePartner(id: string) {
  return useQuery<Partner>({
    queryKey: [PARTNERS_KEY, id],
    queryFn: async () => {
      const { data } = await partnersApi.get(id);
      return data;
    },
    enabled: Boolean(id),
  });
}

export function useCreatePartner() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Partner>) => partnersApi.create(data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: [PARTNERS_KEY] }),
  });
}

export function useUpdatePartner(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Partner>) => partnersApi.update(id, data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [PARTNERS_KEY] });
      qc.invalidateQueries({ queryKey: [PARTNERS_KEY, id] });
    },
  });
}

export function useDeletePartner() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => partnersApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [PARTNERS_KEY] }),
  });
}

export function usePartnerScore(id: string) {
  return useQuery({
    queryKey: [PARTNERS_KEY, id, "score"],
    queryFn: async () => {
      const { data } = await partnersApi.getScore(id);
      return data;
    },
    enabled: Boolean(id),
  });
}

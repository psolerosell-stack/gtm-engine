import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  OverviewKPIs,
  FunnelStage,
  PartnerPerformance,
  MonthlyARR,
  DailyBriefing,
  analyticsApi,
} from "@/api/client";

export function useOverviewKPIs() {
  return useQuery<OverviewKPIs>({
    queryKey: ["analytics", "overview"],
    queryFn: async () => {
      const { data } = await analyticsApi.overview();
      return data;
    },
  });
}

export function useFunnelStats() {
  return useQuery<FunnelStage[]>({
    queryKey: ["analytics", "funnel"],
    queryFn: async () => {
      const { data } = await analyticsApi.funnel();
      return data;
    },
  });
}

export function usePartnerPerformance(limit = 10) {
  return useQuery<PartnerPerformance[]>({
    queryKey: ["analytics", "partnerPerformance", limit],
    queryFn: async () => {
      const { data } = await analyticsApi.partnerPerformance(limit);
      return data;
    },
  });
}

export function useARRTrends(months = 12) {
  return useQuery<MonthlyARR[]>({
    queryKey: ["analytics", "revenueTrends", months],
    queryFn: async () => {
      const { data } = await analyticsApi.revenueTrends(months);
      return data;
    },
  });
}

export function useBriefingToday() {
  return useQuery<DailyBriefing | null>({
    queryKey: ["analytics", "briefing", "today"],
    queryFn: async () => {
      try {
        const { data } = await analyticsApi.briefingToday();
        return data;
      } catch (err: unknown) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 404) return null;
        throw err;
      }
    },
  });
}

export function useGenerateBriefing() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => analyticsApi.generateBriefing().then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["analytics", "briefing"] }),
  });
}

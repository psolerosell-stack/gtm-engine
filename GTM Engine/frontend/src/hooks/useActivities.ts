import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, activitiesApi } from "@/api/client";

const ACT_KEY = "activities";

interface ActivitiesFilters {
  entity_type?: string;
  entity_id?: string;
  type?: string;
  limit?: number;
  offset?: number;
}

export function useActivities(filters: ActivitiesFilters = {}) {
  return useQuery<Activity[]>({
    queryKey: [ACT_KEY, filters],
    queryFn: async () => {
      const { data } = await activitiesApi.list(
        filters as Record<string, string | number | undefined>
      );
      return data;
    },
    enabled: !filters.entity_id || Boolean(filters.entity_id),
  });
}

export function useCreateActivity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Activity>) =>
      activitiesApi.create(data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: [ACT_KEY] }),
  });
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Account, PaginatedResponse, accountsApi } from "@/api/client";

const ACC_KEY = "accounts";

interface AccountsFilters {
  page?: number;
  page_size?: number;
  name?: string;
  industry?: string;
  erp_ecosystem?: string;
  geography?: string;
}

export function useAccounts(filters: AccountsFilters = {}) {
  return useQuery<PaginatedResponse<Account>>({
    queryKey: [ACC_KEY, filters],
    queryFn: async () => {
      const { data } = await accountsApi.list(
        filters as Record<string, string | number | undefined>
      );
      return data;
    },
  });
}

export function useAccount(id: string) {
  return useQuery<Account>({
    queryKey: [ACC_KEY, id],
    queryFn: async () => {
      const { data } = await accountsApi.get(id);
      return data;
    },
    enabled: Boolean(id),
  });
}

export function useEnrichAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, force }: { id: string; force?: boolean }) =>
      accountsApi.enrich(id, force),
    onSuccess: () => qc.invalidateQueries({ queryKey: [ACC_KEY] }),
  });
}

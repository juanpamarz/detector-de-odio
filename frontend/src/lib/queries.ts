import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, type Params } from "./api";
import { usePeriod } from "./period";
import type { BotStatus, CategorySlice, Group, HeatCell, Incident, Overview, Page, StackedRow, TimePoint, User } from "./types";

function useScope(groupId?: number): Params {
  const { days, tz } = usePeriod();
  return { days, tz, group_id: groupId };
}

const REFRESH = 30_000; // el panel se actualiza solo cada 30 s

export function useOverview(groupId?: number) {
  const p = useScope(groupId);
  return useQuery({ queryKey: ["overview", p], queryFn: () => api<Overview>("/analytics/overview", { params: p }), refetchInterval: REFRESH });
}

export function useDistribution(groupId?: number) {
  const p = useScope(groupId);
  return useQuery({ queryKey: ["distribution", p], queryFn: () => api<CategorySlice[]>("/analytics/distribution", { params: p }), refetchInterval: REFRESH });
}

export function useTimeseries(granularity: "hour" | "day", groupId?: number) {
  const p = { ...useScope(groupId), granularity };
  return useQuery({
    queryKey: ["timeseries", p],
    queryFn: () => api<TimePoint[]>("/analytics/timeseries", { params: p }),
    refetchInterval: REFRESH,
    placeholderData: keepPreviousData,
  });
}

export function useTopUsers(groupId?: number) {
  const p = useScope(groupId);
  return useQuery({ queryKey: ["top-users", p], queryFn: () => api<StackedRow[]>("/analytics/top-users", { params: p }) });
}

export function useGroupRanking() {
  const p = useScope();
  return useQuery({ queryKey: ["groups-ranking", p], queryFn: () => api<StackedRow[]>("/analytics/groups-ranking", { params: p }) });
}

export function useHeatmap(groupId?: number) {
  const p = useScope(groupId);
  return useQuery({ queryKey: ["heatmap", p], queryFn: () => api<HeatCell[]>("/analytics/heatmap", { params: p }) });
}

export function useGroups() {
  const p = useScope();
  return useQuery({ queryKey: ["groups", p], queryFn: () => api<Group[]>("/groups", { params: p }), refetchInterval: REFRESH });
}

export function useGroup(id: number) {
  const p = useScope();
  return useQuery({ queryKey: ["group", id, p], queryFn: () => api<Group>(`/groups/${id}`, { params: p }) });
}

export function useIncidents(params: Params) {
  return useQuery({
    queryKey: ["incidents", params],
    queryFn: () => api<Page<Incident>>("/incidents", { params }),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH,
  });
}

export function useUsers() {
  return useQuery({ queryKey: ["users"], queryFn: () => api<User[]>("/users") });
}

export function useBotStatus() {
  return useQuery({ queryKey: ["bot-status"], queryFn: () => api<BotStatus>("/bot/status"), refetchInterval: 60_000, retry: 0 });
}

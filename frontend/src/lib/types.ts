export type Role = "admin" | "moderator" | "analyst";

export type MacroCategory = "identity_hate" | "aggression" | "sexual" | "crisis" | "none";

export type HateCategory =
  | "racism"
  | "xenophobia"
  | "misogyny"
  | "lgbtq_phobia"
  | "religious"
  | "ableism"
  | "identity_other"
  | "insult"
  | "harassment"
  | "threat"
  | "sexual"
  | "self_harm"
  | "none";

export type ActionTaken = "deleted_warned" | "deleted_banned" | "deleted_crisis_support" | "logged_only";
export type UserResponse = "withdrawn" | "republished";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface Overview {
  analyzed: number;
  incidents: number;
  incidents_prev: number;
  crisis: number;
  users_sanctioned: number;
  users_banned: number;
  active_groups: number;
  incident_rate: number;
  mean_toxicity: number;
  withdrawn: number;
  republished: number;
}

export interface CategorySlice {
  macro: MacroCategory;
  category: HateCategory;
  count: number;
}

export interface TimePoint {
  bucket: string;
  analyzed: number;
  incidents: number;
  identity_hate: number;
  aggression: number;
  sexual: number;
  crisis: number;
}

export interface StackedRow {
  id: number;
  label: string;
  identity_hate: number;
  aggression: number;
  sexual: number;
  crisis: number;
  total: number;
  extra: Record<string, number | boolean | null>;
}

export interface HeatCell {
  weekday: number;
  hour: number;
  count: number;
}

export interface Group {
  id: number;
  title: string;
  chat_type: string;
  is_active: boolean;
  toxicity_threshold: number | null;
  effective_threshold: number;
  last_activity_at: string | null;
  analyzed: number;
  incidents: number;
  crisis: number;
  banned: number;
  incident_rate: number;
  bot_status: string | null;
  can_delete: boolean | null;
  can_restrict: boolean | null;
  member_count: number | null;
  checked_at: string | null;
}

export interface ProviderHealth {
  name: string;
  role: "primario" | "respaldo";
  available: boolean;
  cooldown_seconds: number;
}

export interface BotStatus {
  username: string | null;
  name: string | null;
  privacy_mode: boolean;
  can_join_groups: boolean;
  mode: "webhook" | "polling";
  queue_backend: "celery" | "qstash";
  webhook_url: string | null;
  expected_webhook_url: string | null;
  pending_updates: number;
  last_error: string | null;
  last_error_at: string | null;
  providers: ProviderHealth[];
}

export interface ProviderTrace {
  name: string;
  toxicity?: number;
  crisis?: number;
  latency_ms?: number;
  error?: string;
}

export interface Incident {
  id: number;
  created_at: string;
  message_sent_at: string;
  group_id: number;
  group_title: string;
  user_id: number;
  user_display: string;
  message_text: string;
  is_text_redacted: boolean;
  category: HateCategory;
  macro_category: MacroCategory;
  toxicity_score: number;
  crisis_score: number;
  action: ActionTaken;
  user_response: UserResponse | null;
  providers: ProviderTrace[];
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

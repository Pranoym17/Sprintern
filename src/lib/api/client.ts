import { apiUrl } from "@/lib/env";
import type { Analytics, FilterInput, JobFilter, JobMatch, MatchPage, MatchStatus, Profile, ProfileUpdate, TelegramLink } from "./types";

export class ApiError extends Error {
  constructor(public status:number, public code:string, message:string, public details?:unknown) { super(message); this.name = "ApiError"; }
}

export class ApiClient {
  constructor(private getToken: () => Promise<string | null>) {}
  async request<T>(path:string, init:RequestInit = {}):Promise<T> {
    const token = await this.getToken();
    if (!token) throw new ApiError(401, "not_authenticated", "Your session has expired. Please sign in again.");
    let response:Response;
    try { response = await fetch(`${apiUrl}${path}`, { ...init, cache:"no-store", headers:{ Authorization:`Bearer ${token}`, ...(init.body ? {"Content-Type":"application/json"} : {}), ...init.headers } }); }
    catch { throw new ApiError(0, "network_error", "Sprintern could not reach the API. Check that it is running and try again."); }
    if (response.status === 204) return undefined as T;
    const body = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = body?.error ?? body;
      const message = detail?.message ?? (typeof detail?.detail === "string" ? detail.detail : "Something went wrong. Please try again.");
      throw new ApiError(response.status, detail?.code ?? "request_failed", message, detail?.details ?? detail?.detail);
    }
    return body as T;
  }
  profile = () => this.request<Profile>("/users/me");
  updateProfile = (value:ProfileUpdate) => this.request<Profile>("/users/me", {method:"PATCH", body:JSON.stringify(value)});
  createTelegramLink = () => this.request<TelegramLink>("/users/me/telegram-link", {method:"POST"});
  unlinkTelegram = () => this.request<void>("/users/me/telegram-link", {method:"DELETE"});
  filters = () => this.request<JobFilter[]>("/filters");
  createFilter = (value:FilterInput) => this.request<JobFilter>("/filters", {method:"POST", body:JSON.stringify(value)});
  updateFilter = (id:string, value:Partial<FilterInput>) => this.request<JobFilter>(`/filters/${id}`, {method:"PATCH", body:JSON.stringify(value)});
  deleteFilter = (id:string) => this.request<void>(`/filters/${id}`, {method:"DELETE"});
  matches = (cursor?:string) => this.request<MatchPage>(`/matches?limit=25${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`);
  updateMatch = (id:string, status:MatchStatus) => this.request<JobMatch>(`/matches/${id}`, {method:"PATCH", body:JSON.stringify({status})});
  analytics = () => this.request<Analytics>("/analytics/summary");
}

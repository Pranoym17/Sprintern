import { apiUrl } from "@/lib/env";
import type { AccountExport, Analytics, FilterInput, JobFilter, JobMatch, MatchPage, MatchStatus, Profile, ProfileUpdate, SourceHealth, TelegramLink } from "./types";

export class ApiError extends Error {
  constructor(public status:number, public code:string, message:string, public details?:unknown) { super(message); this.name = "ApiError"; }
}

export class ApiClient {
  private handlingUnauthorized = false;
  constructor(
    private getToken: () => Promise<string | null>,
    private onUnauthorized?: () => Promise<void> | void,
    private timeoutMs = 12_000,
  ) {}
  async request<T>(path:string, init:RequestInit = {}):Promise<T> {
    const token = await this.getToken();
    if (!token) throw new ApiError(401, "not_authenticated", "Your session has expired. Please sign in again.");
    let response:Response;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), this.timeoutMs);
    const abortFromCaller = () => controller.abort();
    init.signal?.addEventListener("abort", abortFromCaller, { once: true });
    try { response = await fetch(`${apiUrl}${path}`, { ...init, signal:controller.signal, cache:"no-store", headers:{ Authorization:`Bearer ${token}`, ...(init.body ? {"Content-Type":"application/json"} : {}), ...init.headers } }); }
    catch {
      if (controller.signal.aborted) throw new ApiError(0, "request_timeout", "The API took too long to respond. Please try again.");
      throw new ApiError(0, "network_error", "Sprintern could not reach the API. Check that it is running and try again.");
    } finally { window.clearTimeout(timeout); init.signal?.removeEventListener("abort", abortFromCaller); }
    if (response.status === 204) return undefined as T;
    const body = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = body?.error ?? body;
      const message = detail?.message ?? (typeof detail?.detail === "string" ? detail.detail : "Something went wrong. Please try again.");
      if (response.status === 401 && this.onUnauthorized && !this.handlingUnauthorized) {
        this.handlingUnauthorized = true;
        try { await this.onUnauthorized(); } finally { this.handlingUnauthorized = false; }
      }
      throw new ApiError(response.status, detail?.code ?? "request_failed", message, detail?.details ?? detail?.detail);
    }
    return body as T;
  }
  profile = () => this.request<Profile>("/users/me");
  updateProfile = (value:ProfileUpdate) => this.request<Profile>("/users/me", {method:"PATCH", body:JSON.stringify(value)});
  createTelegramLink = () => this.request<TelegramLink>("/users/me/telegram-link", {method:"POST"});
  unlinkTelegram = () => this.request<void>("/users/me/telegram-link", {method:"DELETE"});
  exportAccount = () => this.request<AccountExport>("/users/me/export");
  deleteAccount = () => this.request<void>("/users/me", {method:"DELETE", body:JSON.stringify({confirmation:"DELETE"})});
  sourceHealth = () => this.request<SourceHealth>("/sources/status");
  filters = () => this.request<JobFilter[]>("/filters");
  createFilter = (value:FilterInput) => this.request<JobFilter>("/filters", {method:"POST", body:JSON.stringify(value)});
  updateFilter = (id:string, value:Partial<FilterInput>) => this.request<JobFilter>(`/filters/${id}`, {method:"PATCH", body:JSON.stringify(value)});
  deleteFilter = (id:string) => this.request<void>(`/filters/${id}`, {method:"DELETE"});
  matches = (cursor?:string, status?:MatchStatus) => this.request<MatchPage>(`/matches?limit=25${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}${status ? `&status=${status}` : ""}`);
  updateMatch = (id:string, status:MatchStatus) => this.request<JobMatch>(`/matches/${id}`, {method:"PATCH", body:JSON.stringify({status})});
  analytics = () => this.request<Analytics>("/analytics/summary");
}

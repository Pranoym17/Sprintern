import { apiUrl } from "@/lib/env";
import type { AccountExport, Analytics, Application, ApplicationStage, Collection, CompanyWatchlist, CSVImportResult, DeliveryChannel, DeliveryQueue, FilterInput, FilterNotification, FilterPreview, Job, JobFilter, JobInteraction, JobMatch, MatchPage, MatchSort, MatchStatus, Profile, ProfileUpdate, ShareLink, SourceHealth, TelegramLink, WeeklyProgress } from "./types";

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
  async download(path:string, filename:string) {
    const token = await this.getToken();
    if (!token) throw new ApiError(401, "not_authenticated", "Please sign in again.");
    const response = await fetch(`${apiUrl}${path}`, {headers:{Authorization:`Bearer ${token}`}});
    if (!response.ok) throw new ApiError(response.status, "download_failed", "Could not create export.");
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = filename; anchor.click();
    URL.revokeObjectURL(url);
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
  previewFilter = (value:FilterInput) => this.request<FilterPreview>("/filters/preview", {method:"POST", body:JSON.stringify(value)});
  filterNotifications = (id:string) => this.request<FilterNotification>(`/filters/${id}/notifications`);
  updateFilterNotifications = (id:string, value:Omit<FilterNotification,"filter_id"|"uses_profile_defaults">) => this.request<FilterNotification>(`/filters/${id}/notifications`, {method:"PUT", body:JSON.stringify(value)});
  notificationQueue = () => this.request<DeliveryQueue>("/notifications/queue");
  testNotification = (channel:DeliveryChannel) => this.request<{channel:DeliveryChannel;outcome:string;error:string|null}>("/notifications/test", {method:"POST", body:JSON.stringify({channel})});
  watchlists = () => this.request<CompanyWatchlist[]>("/watchlists");
  createWatchlist = (value:{company:string;terms:string[];locations:string[];active:boolean}) => this.request<CompanyWatchlist>("/watchlists", {method:"POST", body:JSON.stringify(value)});
  updateWatchlist = (id:string, value:Record<string,unknown>) => this.request<CompanyWatchlist>(`/watchlists/${id}`, {method:"PATCH", body:JSON.stringify(value)});
  deleteWatchlist = (id:string) => this.request<void>(`/watchlists/${id}`, {method:"DELETE"});
  matches = (cursor?:string, status?:MatchStatus, query="", sort:MatchSort="newest", collection?:Collection, includeHidden=false) => this.request<MatchPage>(`/matches?limit=25${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}${status ? `&status=${status}` : ""}${query ? `&query=${encodeURIComponent(query)}` : ""}&sort=${sort}${collection ? `&collection=${collection}` : ""}${includeHidden ? "&include_hidden=true" : ""}`);
  updateMatch = (id:string, status:MatchStatus) => this.request<JobMatch>(`/matches/${id}`, {method:"PATCH", body:JSON.stringify({status})});
  interactions = () => this.request<JobInteraction[]>("/job-interactions");
  updateInteraction = (jobId:string, value:Record<string,unknown>) => this.request<JobInteraction>(`/jobs/${jobId}/interaction`, {method:"PATCH", body:JSON.stringify(value)});
  recordView = (jobId:string) => this.request<JobInteraction>(`/jobs/${jobId}/view`, {method:"POST"});
  reportJob = (jobId:string, reason:string) => this.request(`/jobs/${jobId}/reports`, {method:"POST", body:JSON.stringify({reason})});
  shareJob = (jobId:string) => this.request<ShareLink>(`/jobs/${jobId}/shares`, {method:"POST", body:JSON.stringify({expires_in_hours:72})});
  similarJobs = (jobId:string) => this.request<Job[]>(`/jobs/${jobId}/similar`);
  applications = (stage?:ApplicationStage) => this.request<Application[]>(`/applications${stage ? `?stage=${stage}` : ""}`);
  updateApplication = (id:string, value:Record<string,unknown>) => this.request<Application>(`/applications/${id}`, {method:"PATCH", body:JSON.stringify(value)});
  deleteApplication = (id:string) => this.request<void>(`/applications/${id}`, {method:"DELETE"});
  importApplications = (csvText:string, mapping:Record<string,string>, dryRun:boolean) => this.request<CSVImportResult>("/imports/applications/csv", {method:"POST", body:JSON.stringify({csv_text:csvText,mapping,dry_run:dryRun})});
  weeklyGoal = () => this.request<WeeklyProgress>("/goals/weekly");
  updateWeeklyGoal = (value:{target:number;reminders_enabled:boolean;streaks_enabled:boolean}) => this.request<WeeklyProgress>("/goals/weekly", {method:"PUT", body:JSON.stringify(value)});
  analytics = () => this.request<Analytics>("/analytics/summary");
}

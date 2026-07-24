import type { components } from "./schema";

type Schemas = components["schemas"];

export type WorkMode = Schemas["WorkMode"];
export type MatchStatus = Schemas["MatchStatus"];
export type NotificationCadence = Schemas["NotificationCadence"];
export type DeliveryChannel = Schemas["NotificationChannel"];
export type DeliveryStatus = Schemas["DeliveryStatus"];
export type ApplicationStage = Schemas["ApplicationStage"];

export type Profile = Schemas["ProfileResponse"];
export type ProfileUpdate = Schemas["ProfileUpdate"];
export type Job = Schemas["PublicJobResponse"];
export type DeliverySummary = Schemas["DeliverySummary"];
export type JobMatch = Schemas["MatchResponse"];
export type MatchCounts = Schemas["MatchCounts"];
export type MatchPage = Schemas["MatchPage"];
export type FilterExclusion = Schemas["FilterExclusionResponse"];
export type JobFilter = Schemas["FilterResponse"];
export type FilterInput = Schemas["FilterCreate"];
export type FilterPreview = Schemas["FilterPreviewResponse"];
export type FilterNotification = Schemas["FilterNotificationResponse"];
export type DeliveryQueue = Schemas["DeliveryQueueSummary"];
export type CompanyWatchlist = Schemas["WatchlistResponse"];
export type ApplicationEvent = Schemas["ApplicationEventResponse"];
export type Application = Schemas["ApplicationResponse"];
export type WeeklyProgress = Schemas["WeeklyProgress"];
export type CSVImportResult = Schemas["CSVImportResponse"];
export type JobInteraction = Schemas["InteractionResponse"];
export type ShareLink = Schemas["ShareResponse"];
export type Analytics = Schemas["AnalyticsSummary"];
export type TelegramLink = Schemas["TelegramLinkResponse"];
export type SourceHealth = Schemas["PublicSourceStatus"];
export type AccountExport = Schemas["AccountExportResponse"];
export type AdminSource = Schemas["AdminSourceResponse"];
export type AdminSourceInput = Schemas["AdminSourceCreate"];
export type SourcePreview = Schemas["SourcePreviewResponse"];
export type AdminSourceRun = Schemas["AdminRunResponse"];
export type SourceAudit = Schemas["SourceAuditResponse"];

export type MatchReason = Record<string, unknown>;
export type MatchSort = "newest" | "company" | "relevance" | "deadline";
export type Collection =
  | "toronto"
  | "remote"
  | "canadian"
  | "new-week"
  | "closing-soon"
  | "reopened"
  | "followed-companies"
  | "strongest"
  | "recently-viewed";

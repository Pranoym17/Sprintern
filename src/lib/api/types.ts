export type WorkMode = "remote" | "onsite" | "hybrid" | "any" | "unknown";
export type MatchStatus = "matched" | "applied" | "dismissed";
export type NotificationCadence = "instant" | "hourly" | "daily" | "weekly";
export type DeliveryChannel = "email" | "telegram";
export type DeliveryStatus = "pending" | "sending" | "sent" | "failed" | "cancelled";

export interface Profile { id:string; email:string|null; timezone:string; notification_cadence:NotificationCadence; telegram_chat_id:string|null; email_notifications_enabled:boolean; email_notifications_consent_at:string|null; email_suppressed_at:string|null; email_suppression_reason:string|null; telegram_notifications_enabled:boolean; created_at:string; updated_at:string; }
export interface ProfileUpdate { timezone?:string; notification_cadence?:NotificationCadence; email_notifications_enabled?:boolean; telegram_notifications_enabled?:boolean; }
export interface JobSource { source:string; external_id:string; source_url:string|null; apply_url:string; }
export interface Job { id:string; company:string; title:string; location:string|null; term:string|null; description:string|null; work_mode:WorkMode; status:"active"|"stale"|"expired"; posted_at:string|null; first_seen_at:string; last_seen_at:string; reopened_at:string|null; deadline_at:string|null; deadline_source:"source"|"inferred"|"user"|null; title_incomplete:boolean; latitude:number|null; longitude:number|null; sources:JobSource[]; }
export interface MatchReason { filter_id?:string; filter_name?:string; matcher_version?:string; dimensions?:Record<string,string>; }
export interface DeliverySummary { channel:DeliveryChannel; status:DeliveryStatus; sent_at:string|null; }
export interface JobMatch { id:string; profile_id:string; reasons:MatchReason[]; status:MatchStatus; applied_at:string|null; created_at:string; updated_at:string; job:Job; deliveries:DeliverySummary[]; }
export interface MatchCounts { all:number; matched:number; applied:number; dismissed:number; }
export interface MatchPage { items:JobMatch[]; next_cursor:string|null; counts:MatchCounts; }
export interface FilterExclusion { kind:"keyword"|"company"|"location"; value:string; }
export interface JobFilter { id:string; profile_id:string; name:string; role_keywords:string[]; location_keywords:string[]; terms:string[]; work_mode:WorkMode; active:boolean; remote_only:boolean; radius_km:number|null; center_latitude:number|null; center_longitude:number|null; exclusions:FilterExclusion[]; created_at:string; updated_at:string; }
export interface FilterInput { name:string; role_keywords:string[]; location_keywords:string[]; terms:string[]; work_mode:WorkMode; active:boolean; remote_only?:boolean; radius_km?:number|null; center_latitude?:number|null; center_longitude?:number|null; excluded_keywords?:string[]; excluded_companies?:string[]; excluded_locations?:string[]; }
export interface FilterPreview { estimated_count:number; examples:{id:string;company:string;title:string;location:string|null;reasons:Record<string,unknown>}[]; warnings:string[]; aliases:Record<string,string[]>; exclusions:Record<string,string[]>; }
export interface CompanyWatchlist { id:string; company:string; terms:string[]; locations:string[]; active:boolean; created_at:string; updated_at:string; }
export type ApplicationStage = "saved"|"preparing"|"applied"|"oa"|"interview"|"offer"|"rejected"|"withdrawn";
export interface ApplicationEvent { id:string; event_type:string; data:Record<string,unknown>; corrected_event_id:string|null; created_at:string; }
export interface Application { id:string; profile_id:string; stage:ApplicationStage; notes:string|null; deadline_at:string|null; follow_up_at:string|null; interview_at:string|null; contact:string|null; resume_version:string|null; application_url:string|null; applied_at:string|null; outcome:string|null; created_at:string; updated_at:string; job:Job; events:ApplicationEvent[]; }
export interface WeeklyProgress { target:number; applied:number; interviews:number; offers:number; current_streak:number; best_streak:number; reminders_enabled:boolean; streaks_enabled:boolean; }
export interface CSVImportResult { total_rows:number; valid_rows:number; imported_rows:number; duplicate_rows:number; errors:{row:number;status:string;message:string}[]; detected_columns:string[]; }
export type MatchSort = "newest"|"company"|"relevance"|"deadline";
export type Collection = "toronto"|"remote"|"canadian"|"new-week"|"closing-soon"|"reopened"|"followed-companies"|"strongest"|"recently-viewed";
export interface JobInteraction { job_id:string; bookmarked_at:string|null; hidden_at:string|null; not_interested_reason:string|null; first_viewed_at:string|null; last_viewed_at:string|null; view_count:number; deadline_override_at:string|null; }
export interface ShareLink { id:string; url:string; expires_at:string; }
export interface Analytics { matched_count:number; applied_count:number; average_seconds_to_apply:number|null; }
export interface TelegramLink { token:string; deep_link:string; expires_at:string; }
export interface SourceHealth { state:"healthy"|"stale"|"unknown"; last_updated_at:string|null; }
export interface AccountExport { exported_at:string; profile:unknown; filters:unknown[]; matches:unknown[]; }

export type WorkMode = "remote" | "onsite" | "hybrid" | "any" | "unknown";
export type MatchStatus = "matched" | "applied" | "dismissed";
export type NotificationCadence = "instant" | "hourly" | "daily";

export interface Profile { id:string; email:string|null; timezone:string; notification_cadence:NotificationCadence; telegram_chat_id:string|null; email_notifications_enabled:boolean; telegram_notifications_enabled:boolean; created_at:string; updated_at:string; }
export interface ProfileUpdate { timezone?:string; notification_cadence?:NotificationCadence; email_notifications_enabled?:boolean; telegram_notifications_enabled?:boolean; }
export interface JobSource { source:string; external_id:string; source_url:string|null; apply_url:string; }
export interface Job { id:string; company:string; title:string; location:string|null; term:string|null; description:string|null; work_mode:WorkMode; status:"active"|"stale"|"expired"; posted_at:string|null; first_seen_at:string; last_seen_at:string; sources:JobSource[]; }
export interface MatchReason { filter_id?:string; filter_name?:string; matcher_version?:string; dimensions?:Record<string,string>; }
export interface JobMatch { id:string; profile_id:string; reasons:MatchReason[]; status:MatchStatus; applied_at:string|null; created_at:string; updated_at:string; job:Job; }
export interface MatchCounts { all:number; matched:number; applied:number; dismissed:number; }
export interface MatchPage { items:JobMatch[]; next_cursor:string|null; counts:MatchCounts; }
export interface JobFilter { id:string; profile_id:string; name:string; role_keywords:string[]; location_keywords:string[]; terms:string[]; work_mode:WorkMode; active:boolean; created_at:string; updated_at:string; }
export interface FilterInput { name:string; role_keywords:string[]; location_keywords:string[]; terms:string[]; work_mode:WorkMode; active:boolean; }
export interface Analytics { matched_count:number; applied_count:number; average_seconds_to_apply:number|null; }
export interface TelegramLink { token:string; deep_link:string; expires_at:string; }

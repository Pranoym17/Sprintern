import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FiltersView } from "./filters-view";
import { MatchesView } from "./matches-view";
import { SettingsView } from "./settings-view";

const notify = vi.fn();
const signOut = vi.fn();
let api: Record<string, ReturnType<typeof vi.fn>>;
vi.mock("./app-provider", () => ({ useApp: () => ({ api, notify, signOut }) }));

const profile = { id:"profile",email:"student@example.com",timezone:"America/Toronto",notification_cadence:"instant",telegram_chat_id:"123",email_notifications_enabled:false,email_notifications_consent_at:null,email_suppressed_at:null,email_suppression_reason:null,preferred_email_time:"08:00:00",email_digest_job_limit:7,email_empty_digest_enabled:false,telegram_notifications_enabled:true,quiet_hours_start:null,quiet_hours_end:null,weekend_pause:false,max_alerts_per_day:25,priority_only_instant:false,notification_consents:{},created_at:"2026-01-01",updated_at:"2026-01-01" };
const match = { id:"match-1",profile_id:"profile",reasons:[{dimensions:{role:"software"}}],status:"matched",applied_at:null,created_at:"2026-07-01",updated_at:"2026-07-01",job:{id:"job-1",company:"Acme",title:"Software Intern",location:"Toronto",term:"Summer 2027",description:null,work_mode:"hybrid",status:"active",posted_at:"2026-07-01",first_seen_at:"2026-07-01",last_seen_at:"2026-07-01",reopened_at:null,deadline_at:null,deadline_is_estimated:false,title_incomplete:false,latitude:null,longitude:null,application_url:"https://example.com/apply"}};

beforeEach(() => {
  notify.mockReset();
  signOut.mockReset();
  api = {
    matches: vi.fn(async (_cursor, status) => ({ items: status === "applied" ? [{...match,id:"applied-1",status:"applied"}] : [match], next_cursor:null, counts:{all:2,matched:1,applied:1,dismissed:0} })),
    updateMatch: vi.fn(async (_id, status) => ({...match,status})),
    interactions: vi.fn(async () => []),
    updateInteraction: vi.fn(), recordView: vi.fn(async () => undefined), reportJob: vi.fn(), shareJob: vi.fn(), similarJobs:vi.fn(async () => []),
    filters: vi.fn(async () => []), createFilter:vi.fn(async (value) => ({...value,id:"filter",profile_id:"profile",created_at:"",updated_at:""})), updateFilter:vi.fn(), deleteFilter:vi.fn(),
    previewFilter:vi.fn(async () => ({estimated_count:1,examples:[],warnings:[],aliases:{},exclusions:{}})), watchlists:vi.fn(async () => []), createWatchlist:vi.fn(), updateWatchlist:vi.fn(), deleteWatchlist:vi.fn(),
    profile:vi.fn(async () => profile), updateProfile:vi.fn(async (value) => ({...profile,...value})), notificationQueue:vi.fn(async () => ({pending:0,delayed_by_quiet_hours:0,delayed_by_weekend:0,delayed_by_daily_cap:0,failed:0,suppressed:0})), adminAccess:vi.fn(async () => { throw new Error("not admin"); }), testNotification:vi.fn(), createTelegramLink:vi.fn(), unlinkTelegram:vi.fn(), exportAccount:vi.fn(), deleteAccount:vi.fn(async () => undefined), sourceHealth:vi.fn(async () => ({state:"healthy",last_updated_at:"2026-07-01"})),
  };
});
afterEach(cleanup);

describe("authenticated product workflows", () => {
  it("loads authoritative status pages and applies a match without confirmation", async () => {
    const user = userEvent.setup(); render(<MatchesView />);
    await screen.findByText("Software Intern");
    await user.click(screen.getByRole("button", { name:/mark applied/i }));
    expect(api.updateMatch).toHaveBeenCalledWith("match-1", "applied");
    await user.click(screen.getByRole("button", { name:/applied/i }));
    await waitFor(() => expect(api.matches).toHaveBeenCalledWith(undefined, "applied", "", "newest", undefined, false));
  });

  it("records deliberate job views and lets hidden jobs be recovered", async () => {
    const user = userEvent.setup();
    api.interactions = vi.fn(async () => [{
      id:"interaction", profile_id:"profile", job_id:"job-1", bookmarked_at:null,
      hidden_at:"2026-07-01", not_interested_reason:null, deadline_override_at:null,
      last_viewed_at:null, view_count:0, created_at:"", updated_at:"",
    }]);
    api.updateInteraction = vi.fn(async () => ({
      id:"interaction", profile_id:"profile", job_id:"job-1", bookmarked_at:null,
      hidden_at:null, not_interested_reason:null, deadline_override_at:null,
      last_viewed_at:null, view_count:0, created_at:"", updated_at:"",
    }));
    render(<MatchesView />);
    await screen.findByText("Software Intern");
    fireEvent.click(screen.getByRole("link", { name:"Software Intern" }));
    expect(api.recordView).toHaveBeenCalledWith("job-1");
    await user.click(screen.getByRole("button", { name:/hidden jobs/i }));
    await waitFor(() => expect(api.matches).toHaveBeenCalledWith(undefined, undefined, "", "newest", undefined, true));
    await user.click(await screen.findByRole("button", { name:/restore to feed/i }));
    expect(api.updateInteraction).toHaveBeenCalledWith("job-1", { hidden:false });
  });

  it("creates a guided chip filter", async () => {
    const user = userEvent.setup(); render(<FiltersView />);
    await screen.findByText("Create your first signal"); await user.click(screen.getByRole("button", { name:/new filter/i }));
    await user.type(screen.getByLabelText(/name this search/i), "Software internships");
    await user.type(screen.getByLabelText("Roles or fields"), "software{Enter}");
    await user.click(screen.getByRole("button", { name:/save and match/i }));
    await waitFor(() => expect(api.createFilter).toHaveBeenCalledWith(expect.objectContaining({name:"Software internships",role_keywords:["software"]})));
  });

  it("persists channel and daily digest preferences", async () => {
    const user = userEvent.setup(); render(<SettingsView />);
    await screen.findByText("Choose your channels");
    expect(screen.getByText(/enable email alerts to schedule a digest/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/top matches per email/i), { target: { value: "10" } });
    await user.click(screen.getByRole("button", { name:/save preferences/i }));
    await waitFor(() => expect(api.updateProfile).toHaveBeenCalledWith(expect.objectContaining({email_digest_job_limit:10,preferred_email_time:"08:00"})));
  });

  it("requires typed confirmation before deleting an account", async () => {
    const user = userEvent.setup(); render(<SettingsView />);
    await screen.findByText("Your data, your choice");
    const button = screen.getByRole("button", { name:/delete account/i });
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText(/type delete/i), "DELETE");
    await user.click(button);
    await waitFor(() => expect(api.deleteAccount).toHaveBeenCalledOnce());
    expect(signOut).toHaveBeenCalledOnce();
  });
});

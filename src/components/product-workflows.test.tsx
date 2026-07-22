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

const profile = { id:"profile",email:"student@example.com",timezone:"America/Toronto",notification_cadence:"instant",telegram_chat_id:"123",email_notifications_enabled:false,email_notifications_consent_at:null,email_suppressed_at:null,email_suppression_reason:null,telegram_notifications_enabled:true,created_at:"2026-01-01",updated_at:"2026-01-01" };
const match = { id:"match-1",profile_id:"profile",reasons:[{dimensions:{role:"software"}}],status:"matched",applied_at:null,created_at:"2026-07-01",updated_at:"2026-07-01",job:{id:"job-1",company:"Acme",title:"Software Intern",location:"Toronto",term:"Summer 2027",description:null,work_mode:"hybrid",status:"active",posted_at:"2026-07-01",first_seen_at:"2026-07-01",last_seen_at:"2026-07-01",sources:[{source:"github_repo",external_id:"1",source_url:null,apply_url:"https://example.com/apply"}]}};

beforeEach(() => {
  notify.mockReset();
  signOut.mockReset();
  api = {
    matches: vi.fn(async (_cursor, status) => ({ items: status === "applied" ? [{...match,id:"applied-1",status:"applied"}] : [match], next_cursor:null, counts:{all:2,matched:1,applied:1,dismissed:0} })),
    updateMatch: vi.fn(async (_id, status) => ({...match,status})),
    interactions: vi.fn(async () => []),
    updateInteraction: vi.fn(), recordView: vi.fn(), reportJob: vi.fn(), shareJob: vi.fn(), similarJobs:vi.fn(async () => []),
    filters: vi.fn(async () => []), createFilter:vi.fn(async (value) => ({...value,id:"filter",profile_id:"profile",created_at:"",updated_at:""})), updateFilter:vi.fn(), deleteFilter:vi.fn(),
    profile:vi.fn(async () => profile), updateProfile:vi.fn(async (value) => ({...profile,...value})), createTelegramLink:vi.fn(), unlinkTelegram:vi.fn(), exportAccount:vi.fn(), deleteAccount:vi.fn(async () => undefined), sourceHealth:vi.fn(async () => ({state:"healthy",last_updated_at:"2026-07-01"})),
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
    await waitFor(() => expect(api.matches).toHaveBeenCalledWith(undefined, "applied", "", "newest", undefined));
  });

  it("creates a guided chip filter", async () => {
    const user = userEvent.setup(); render(<FiltersView />);
    await screen.findByText("Create your first signal"); await user.click(screen.getByRole("button", { name:/new filter/i }));
    await user.type(screen.getByLabelText(/name this search/i), "Software internships");
    await user.type(screen.getByLabelText("Roles or fields"), "software{Enter}");
    await user.click(screen.getByRole("button", { name:/save and match/i }));
    await waitFor(() => expect(api.createFilter).toHaveBeenCalledWith(expect.objectContaining({name:"Software internships",role_keywords:["software"]})));
  });

  it("persists card and segmented notification preferences", async () => {
    const user = userEvent.setup(); render(<SettingsView />);
    await screen.findByText("Choose your channels");
    fireEvent.click(screen.getByLabelText(/hourly/i));
    await user.click(screen.getByRole("button", { name:/save preferences/i }));
    await waitFor(() => expect(api.updateProfile).toHaveBeenCalledWith(expect.objectContaining({notification_cadence:"hourly"})));
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

"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BellRing, CircleUserRound, Filter, LayoutDashboard, LogOut, Settings } from "lucide-react";
import { Brand } from "@/components/brand";
import { useApp } from "@/components/app-provider";

const nav=[{href:"/dashboard",label:"Overview",icon:LayoutDashboard},{href:"/matches",label:"Matches",icon:BellRing},{href:"/filters",label:"Filters",icon:Filter},{href:"/settings",label:"Settings",icon:Settings}];
export function AppShell({children,email}:{children:React.ReactNode;email:string|null}){const path=usePathname();const{signOut}=useApp();return <div className="app-shell"><a className="skip-link" href="#workspace">Skip to content</a><aside className="sidebar"><Brand href="/dashboard"/><nav aria-label="Workspace">{nav.map(({href,label,icon:Icon})=><Link className={path.startsWith(href)?"active":""} href={href} key={href}><Icon size={19}/>{label}</Link>)}</nav><div className="sidebar__account"><CircleUserRound/><span><strong>{email?.split("@")[0]??"Account"}</strong><small>{email??"Signed in"}</small></span><button onClick={signOut} aria-label="Sign out" title="Sign out"><LogOut size={18}/></button></div></aside><div className="workspace"><header className="mobile-header"><Brand href="/dashboard"/><button onClick={signOut} aria-label="Sign out"><LogOut/></button></header><main id="workspace">{children}</main><nav className="mobile-nav" aria-label="Workspace">{nav.map(({href,label,icon:Icon})=><Link className={path.startsWith(href)?"active":""} href={href} key={href}><Icon size={20}/><span>{label}</span></Link>)}</nav></div></div>}

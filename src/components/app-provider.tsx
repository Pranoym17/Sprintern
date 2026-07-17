"use client";
import { createContext, useContext, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiClient } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";

type Notice = { id:number; message:string; tone:"success"|"error" };
const AppContext = createContext<{ api:ApiClient; notify:(message:string,tone?:Notice["tone"])=>void; signOut:()=>Promise<void> } | null>(null);

export function AppProvider({ children }: {children:React.ReactNode}) {
  const router = useRouter(); const [notices,setNotices] = useState<Notice[]>([]);
  const api = useMemo(() => new ApiClient(async () => (await createClient().auth.getSession()).data.session?.access_token ?? null), []);
  function notify(message:string,tone:Notice["tone"]="success") { const id=Date.now(); setNotices(v=>[...v,{id,message,tone}]); window.setTimeout(()=>setNotices(v=>v.filter(n=>n.id!==id)),4000); }
  async function signOut(){ await createClient().auth.signOut(); router.replace("/sign-in"); router.refresh(); }
  return <AppContext.Provider value={{api,notify,signOut}}>{children}<div className="toast-region" aria-live="polite">{notices.map(n=><div className={`toast toast--${n.tone}`} key={n.id}>{n.message}</div>)}</div></AppContext.Provider>;
}
export function useApp(){ const value=useContext(AppContext); if(!value) throw new Error("useApp must be used inside AppProvider"); return value; }

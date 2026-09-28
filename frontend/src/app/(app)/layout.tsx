import { redirect } from "next/navigation";
import { AppProvider } from "@/components/app-provider";
import { AppShell } from "@/components/app-shell";
import { PRODUCT_PAUSED } from "@/lib/product-status";
import { createClient } from "@/lib/supabase/server";

export default async function WorkspaceLayout({children}:{children:React.ReactNode}){if(PRODUCT_PAUSED)redirect("/sign-up");const supabase=await createClient();const{data:{user}}=await supabase.auth.getUser();if(!user)redirect("/sign-in");return <AppProvider><AppShell email={user.email??null}>{children}</AppShell></AppProvider>}

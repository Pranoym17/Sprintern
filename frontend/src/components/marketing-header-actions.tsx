"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { createClient } from "@/lib/supabase/client";

export function MarketingHeaderActions() {
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    let active = true;
    void createClient().auth.getSession().then((result: { data: { session: unknown } }) => {
      if (active) setSignedIn(Boolean(result.data.session));
    });
    return () => { active = false; };
  }, []);

  return signedIn ? (
    <div className="header-actions">
      <Link className="button button--dark button--small" href="/dashboard">Open dashboard <span aria-hidden="true">↗</span></Link>
    </div>
  ) : (
    <div className="header-actions">
      <Link className="text-link" href="/sign-in">Sign in</Link>
      <Link className="button button--dark button--small" href="/sign-up">Start tracking <span aria-hidden="true">↗</span></Link>
    </div>
  );
}

"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { useQuery } from "@tanstack/react-query";
import { api, Organization } from "@/lib/api";
import DashboardPage from "./dashboard/DashboardClient";
import OnboardingPage from "./onboarding/OnboardingClient";
import { Loader2 } from "lucide-react";

export const dynamic = "force-dynamic";

export default function Page() {
  const [mounted, setMounted] = useState(false);
  const { isLoaded, userId, getToken } = useAuth();

  useEffect(() => {
    setMounted(true);
  }, []);

  // Fetch orgs to decide: onboarding vs dashboard
  const { data: orgs, isLoading: orgsLoading, isError } = useQuery<Organization[]>({
    queryKey: ["orgs"],
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error("No token");
      return api.listOrgs(token);
    },
    enabled: !!userId && mounted,
    retry: 2,
    retryDelay: 1000,
  });

  // SSR guard — show spinner until client mounts
  if (!mounted || !isLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <Loader2 className="h-10 w-10 animate-spin text-indigo-500" />
      </div>
    );
  }

  // Still loading orgs
  if (orgsLoading && !orgs && !isError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <div className="flex flex-col items-center space-y-4">
          <Loader2 className="h-10 w-10 animate-spin text-indigo-500" />
          <p className="text-sm text-slate-400">Connecting to backend...</p>
        </div>
      </div>
    );
  }

  // Backend is offline — show dashboard with error banner
  if (isError) {
    return <DashboardPage />;
  }

  // No organizations yet — send to onboarding wizard
  if (!orgs || orgs.length === 0) {
    return <OnboardingPage />;
  }

  // Has orgs — go to dashboard
  return <DashboardPage />;
}

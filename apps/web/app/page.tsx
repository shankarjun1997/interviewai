"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "../lib/auth";
import { Spinner } from "../components/ui/Spinner";

// Entry point: route to the dashboard when authenticated, otherwise to login.
export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace(getToken() ? "/dashboard" : "/login");
  }, [router]);

  return (
    <div className="grid min-h-screen place-items-center">
      <Spinner />
    </div>
  );
}

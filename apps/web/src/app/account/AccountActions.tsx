"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { showToast } from "@/components/ui/toast";

type AccountActionsProps = {
  hasSubscription: boolean;
};

export default function AccountActions({ hasSubscription }: AccountActionsProps) {
  const [isLoading, setIsLoading] = useState(false);

  const startCheckout = async (plan?: "monthly" | "yearly") => {
    setIsLoading(true);
    try {
      const res = await fetch("/api/billing/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      if (data?.url) {
        window.location.href = data.url;
        return;
      }
      throw new Error();
    } catch {
      showToast({ title: "Checkout作成に失敗しました", variant: "error" });
    } finally {
      setIsLoading(false);
    }
  };

  const openPortal = async () => {
    setIsLoading(true);
    try {
      const res = await fetch("/api/billing/portal", { method: "POST" });
      if (!res.ok) throw new Error();
      const data = await res.json();
      if (data?.url) {
        window.location.href = data.url;
        return;
      }
      throw new Error();
    } catch {
      showToast({ title: "Billing Portalに遷移できませんでした", variant: "error" });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-wrap gap-3">
      <Button onClick={() => startCheckout("monthly")} disabled={isLoading}>
        Upgrade（月額）
      </Button>
      <Button onClick={() => startCheckout("yearly")} variant="outline" disabled={isLoading}>
        Upgrade（年額）
      </Button>
      <Button onClick={openPortal} variant="ghost" disabled={isLoading || !hasSubscription}>
        Manage Billing
      </Button>
    </div>
  );
}

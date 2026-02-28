import Link from "next/link";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import AccountActions from "./AccountActions";

const formatDate = (value: string | null) => {
  if (!value) return "不明";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "不明";
  return date.toLocaleDateString("ja-JP");
};

export default async function AccountPage() {
  const supabase = await createSupabaseServerClient();
  const { data } = await supabase.auth.getUser();
  const user = data.user;

  if (!user) {
    return (
      <main className="min-h-screen bg-[#fbf7ef] flex items-center justify-center px-4 py-10">
        <Card className="w-full max-w-lg">
          <CardHeader>
            <CardTitle>アカウント</CardTitle>
            <CardDescription>ログインが必要です。</CardDescription>
          </CardHeader>
          <CardContent>
            <Link className="text-sm text-slate-600 underline" href="/login">
              /login に移動
            </Link>
          </CardContent>
        </Card>
      </main>
    );
  }

  const { data: subscription } = await supabase
    .from("user_subscriptions")
    .select("status, price_id, current_period_end, cancel_at_period_end, stripe_customer_id")
    .eq("user_id", user.id)
    .maybeSingle();

  const status = subscription?.status || "inactive";
  const isPro = ["active", "trialing"].includes(status);

  return (
    <main className="min-h-screen bg-[#fbf7ef] flex items-center justify-center px-4 py-10">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <CardTitle>アカウント</CardTitle>
          <CardDescription>購読状態とBilling管理</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-700">
            <div>ユーザー: {user.email}</div>
            <div>ステータス: {isPro ? "Pro" : "Free"} ({status})</div>
            <div>次回更新: {formatDate(subscription?.current_period_end ?? null)}</div>
            <div>キャンセル予定: {subscription?.cancel_at_period_end ? "はい" : "いいえ"}</div>
          </div>
          <AccountActions hasSubscription={Boolean(subscription?.stripe_customer_id)} />
        </CardContent>
      </Card>
    </main>
  );
}

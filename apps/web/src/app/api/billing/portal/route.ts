import { NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { createSupabaseAdminClient } from "@/lib/supabase/admin";
import { getStripeClient } from "@/lib/stripe";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST() {
  try {
    // まず「誰が叩いてるか」は user セッションで確認（ここはユーザー権限）
    const supabase = await createSupabaseServerClient();
    const { data } = await supabase.auth.getUser();
    const user = data.user;

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    // 次に「stripe_customer_id の参照」だけ admin(service role) で行う（RLSに左右されない）
    const admin = createSupabaseAdminClient();
    const { data: subscriptionRow, error } = await admin
      .from("user_subscriptions")
      .select("stripe_customer_id")
      .eq("user_id", user.id)
      .maybeSingle();

    if (error) {
      console.error("[billing/portal] user_subscriptions read failed:", error);
      return NextResponse.json({ error: "Subscription lookup failed" }, { status: 500 });
    }

    if (!subscriptionRow?.stripe_customer_id) {
      return NextResponse.json({ error: "No billing customer found." }, { status: 400 });
    }

    const stripe = getStripeClient();
    const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

    const session = await stripe.billingPortal.sessions.create({
      customer: subscriptionRow.stripe_customer_id,
      return_url: `${appUrl}/account`,
    });

    return NextResponse.json({ url: session.url });
  } catch (error) {
    console.error("[billing/portal] error:", error);
    return NextResponse.json({ error: "Portal session failed" }, { status: 500 });
  }
}

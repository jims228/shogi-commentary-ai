import { NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { getStripeClient } from "@/lib/stripe";

type CheckoutBody = {
  plan?: "monthly" | "yearly";
  priceId?: string;
};

const resolvePriceId = (body: CheckoutBody) => {
  if (body.priceId) return body.priceId;
  if (body.plan === "yearly") return process.env.STRIPE_PRICE_ID_YEARLY;
  return process.env.STRIPE_PRICE_ID_MONTHLY || process.env.STRIPE_PRICE_ID_YEARLY;
};

export async function POST(request: Request) {
  try {
    const supabase = await createSupabaseServerClient();
    const { data } = await supabase.auth.getUser();
    const user = data.user;

    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const body = (await request.json().catch(() => ({}))) as CheckoutBody;
    const priceId = resolvePriceId(body);

    if (!priceId) {
      return NextResponse.json({ error: "Price ID is not configured." }, { status: 400 });
    }

    const { data: subscriptionRow } = await supabase
      .from("user_subscriptions")
      .select("stripe_customer_id")
      .eq("user_id", user.id)
      .maybeSingle();

    const stripe = getStripeClient();
    const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

    const session = await stripe.checkout.sessions.create({
      mode: "subscription",
      line_items: [{ price: priceId, quantity: 1 }],
      client_reference_id: user.id,
      customer: subscriptionRow?.stripe_customer_id || undefined,
      customer_email: subscriptionRow?.stripe_customer_id ? undefined : user.email || undefined,
      success_url: `${appUrl}/account?checkout=success`,
      cancel_url: `${appUrl}/account?checkout=cancel`,
      metadata: { user_id: user.id },
      subscription_data: {
        metadata: { user_id: user.id },
      },
    });

    return NextResponse.json({ url: session.url });
  } catch (error) {
    console.error("[billing/checkout] error:", error);
    return NextResponse.json({ error: "Checkout failed" }, { status: 500 });
  }
}

import { NextResponse } from "next/server";
import Stripe from "stripe";
import { createSupabaseAdminClient } from "@/lib/supabase/admin";
import { getStripeClient } from "@/lib/stripe";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const toIsoDate = (timestamp: number | null | undefined) => {
  if (!timestamp) return null;
  return new Date(timestamp * 1000).toISOString();
};

const upsertSubscription = async (
  subscription: Stripe.Subscription,
  userId: string | null,
  stripeCustomerId?: string | null
) => {
  if (!userId) {
    console.warn("[billing/webhook] missing user_id for subscription", subscription.id);
    return;
  }

  const supabase = createSupabaseAdminClient();
  const priceId = subscription.items.data[0]?.price?.id ?? null;

  await supabase.from("user_subscriptions").upsert(
    {
      user_id: userId,
      stripe_customer_id: stripeCustomerId ?? subscription.customer?.toString() ?? null,
      stripe_subscription_id: subscription.id,
      status: subscription.status,
      price_id: priceId,
      current_period_end: toIsoDate(subscription.current_period_end),
      cancel_at_period_end: subscription.cancel_at_period_end ?? false,
      updated_at: new Date().toISOString(),
    },
    { onConflict: "user_id" }
  );
};

export async function POST(request: Request) {
  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!webhookSecret) {
    return NextResponse.json({ error: "Webhook secret is not configured." }, { status: 500 });
  }

  const signature = request.headers.get("stripe-signature");
  if (!signature) {
    return NextResponse.json({ error: "Missing Stripe signature." }, { status: 400 });
  }

  const payload = await request.text();
  const stripe = getStripeClient();

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(payload, signature, webhookSecret);
  } catch (error) {
    console.error("[billing/webhook] signature verification failed:", error);
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  try {
    switch (event.type) {
      case "checkout.session.completed": {
        const session = event.data.object as Stripe.Checkout.Session;
        if (session.subscription) {
          const subscription = await stripe.subscriptions.retrieve(
            session.subscription as string
          );
          const userId =
            session.client_reference_id || session.metadata?.user_id || subscription.metadata?.user_id || null;
          await upsertSubscription(subscription, userId, session.customer?.toString() ?? null);
        }
        break;
      }
      case "customer.subscription.created":
      case "customer.subscription.updated":
      case "customer.subscription.deleted": {
        const subscription = event.data.object as Stripe.Subscription;
        const userId = subscription.metadata?.user_id || null;
        await upsertSubscription(subscription, userId, subscription.customer?.toString() ?? null);
        break;
      }
      case "invoice.payment_succeeded":
      case "invoice.payment_failed": {
        const invoice = event.data.object as Stripe.Invoice;
        if (invoice.subscription) {
          const subscription = await stripe.subscriptions.retrieve(
            invoice.subscription as string
          );
          const userId = subscription.metadata?.user_id || null;
          await upsertSubscription(subscription, userId, subscription.customer?.toString() ?? null);
        }
        break;
      }
      default:
        break;
    }
  } catch (error) {
    console.error("[billing/webhook] handler error:", error);
    return NextResponse.json({ error: "Webhook handler failed" }, { status: 500 });
  }

  return NextResponse.json({ received: true });
}

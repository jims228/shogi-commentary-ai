create table if not exists public.user_subscriptions (
  user_id uuid primary key references auth.users(id) on delete cascade,
  stripe_customer_id text unique,
  stripe_subscription_id text unique,
  status text,
  price_id text,
  current_period_end timestamptz,
  cancel_at_period_end boolean default false,
  updated_at timestamptz default now()
);

alter table public.user_subscriptions enable row level security;

create policy "Users can view their own subscription"
on public.user_subscriptions
for select
using (auth.uid() = user_id);

create policy "No direct writes from users"
on public.user_subscriptions
for all
using (false)
with check (false);

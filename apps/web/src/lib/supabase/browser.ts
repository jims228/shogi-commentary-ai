import { createBrowserClient } from "@supabase/ssr";

export const createSupabaseBrowserClient = () => {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !anonKey) {
    const missing = [
      !url ? "NEXT_PUBLIC_SUPABASE_URL" : null,
      !anonKey ? "NEXT_PUBLIC_SUPABASE_ANON_KEY" : null,
    ]
      .filter(Boolean)
      .join(", ");

    throw new Error(
      `Supabase env vars are not set for browser client. Missing: ${missing}. ` +
        `Create apps/web/.env.local and set these values, then restart "pnpm -C apps/web dev".`
    );
  }

  return createBrowserClient(url, anonKey);
};

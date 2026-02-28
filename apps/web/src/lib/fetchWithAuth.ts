import { createSupabaseBrowserClient } from "@/lib/supabase/browser";

export const getSupabaseAccessToken = async () => {
  try {
    const supabase = createSupabaseBrowserClient();
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token ?? null;
  } catch {
    return null;
  }
};

export const fetchWithAuth = async (input: RequestInfo | URL, init: RequestInit = {}) => {
  const token = await getSupabaseAccessToken();
  const headers = new Headers(init.headers);

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return fetch(input, { ...init, headers });
};

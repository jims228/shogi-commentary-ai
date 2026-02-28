"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { createSupabaseBrowserClient } from "@/lib/supabase/browser";

export default function LoginPage() {
  const supabase = useMemo(() => createSupabaseBrowserClient(), []);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSignedIn, setIsSignedIn] = useState(false);

  useEffect(() => {
    const loadSession = async () => {
      const { data } = await supabase.auth.getSession();
      setIsSignedIn(Boolean(data.session));
    };
    loadSession();

    const { data: subscription } = supabase.auth.onAuthStateChange((_event, session) => {
      setIsSignedIn(Boolean(session));
    });
    return () => subscription.subscription.unsubscribe();
  }, [supabase]);

  const handleSignUp = async () => {
    setIsLoading(true);
    setMessage(null);
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      },
    });
    setIsLoading(false);
    if (error) {
      setMessage(error.message);
      return;
    }
    setMessage("サインアップ完了。確認メールを確認してください。");
  };

  const handleSignIn = async () => {
    setIsLoading(true);
    setMessage(null);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setIsLoading(false);
    if (error) {
      setMessage(error.message);
      return;
    }
    setMessage("ログインしました。");
  };

  const handleSignOut = async () => {
    setIsLoading(true);
    setMessage(null);
    await supabase.auth.signOut();
    setIsLoading(false);
    setMessage("ログアウトしました。");
  };

  return (
    <main className="min-h-screen bg-[#fbf7ef] flex items-center justify-center px-4 py-10">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>ログイン</CardTitle>
          <CardDescription>メールアドレスとパスワードでサインインします。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">Email</label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">Password</label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="********"
            />
          </div>
          {message ? <p className="text-sm text-slate-600">{message}</p> : null}
        </CardContent>
        <CardFooter className="flex flex-col gap-3">
          <div className="flex w-full gap-2">
            <Button className="flex-1" onClick={handleSignIn} disabled={isLoading}>
              ログイン
            </Button>
            <Button className="flex-1" variant="outline" onClick={handleSignUp} disabled={isLoading}>
              サインアップ
            </Button>
          </div>
          <Button
            className="w-full"
            variant="ghost"
            onClick={handleSignOut}
            disabled={isLoading || !isSignedIn}
          >
            ログアウト
          </Button>
          <Link className="text-sm text-slate-500 hover:text-slate-700" href="/account">
            アカウントページへ
          </Link>
        </CardFooter>
      </Card>
    </main>
  );
}

This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

### Environment setup (Supabase / Stripe)

Create `apps/web/.env.local` from the example file and fill in values:

```bash
cp apps/web/.env.local.example apps/web/.env.local
```

- In Supabase Dashboard, copy the **Project URL** and **anon public key** into:
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- After editing `.env.local`, restart the dev server to load changes.

First, run the development server:

```bash
pnpm -C apps/web dev
```

WSL 環境で Supabase への接続が `UND_ERR_CONNECT_TIMEOUT` になる場合は、DNS設定を固定するために `pnpm -C apps/web dev:wsl` を使って起動してください（`NODE_OPTIONS=--dns-result-order=ipv4first` を恒久化したコマンドです）。

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

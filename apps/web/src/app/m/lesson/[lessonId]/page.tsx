import { notFound, redirect } from "next/navigation";
import { LESSONS } from "@/constants";

export default async function MobileLessonEntryPage({
  params,
}: {
  // Next.js 16 (App Router) may provide params as a Promise in some configurations.
  params: Promise<{ lessonId: string }> | { lessonId: string };
}) {
  const { lessonId } = await Promise.resolve(params);
  const lesson = LESSONS.find((l) => l.id === lessonId);

  if (!lesson || !lesson.href) notFound();

  const baseHref = lesson.href;
  const join = baseHref.includes("?") ? "&" : "?";
  const mobile = "mobile=1";
  const noai = "noai=1";
  const lid = `lid=${encodeURIComponent(lessonId)}`;
  const next = `${baseHref}${join}${mobile}&${noai}&${lid}`;

  redirect(next);
}



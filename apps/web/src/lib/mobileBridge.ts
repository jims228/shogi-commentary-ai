export function getMobileParamsFromUrl() {
  try {
    if (typeof window === "undefined") return { mobile: false, noai: false, lid: undefined as string | undefined, embed: false };
    const sp = new URLSearchParams(window.location.search);
    return {
      mobile: sp.get("mobile") === "1",
      noai: sp.get("noai") === "1",
      lid: sp.get("lid") ?? undefined,
      embed: sp.get("embed") === "1",
    };
  } catch {
    return { mobile: false, noai: false, lid: undefined as string | undefined, embed: false };
  }
}

export function isMobileWebView() {
  return getMobileParamsFromUrl().mobile;
}

export function syncMobileRootDataAttributes() {
  try {
    if (typeof document === "undefined") return;
    const { mobile, noai } = getMobileParamsFromUrl();
    const el = document.documentElement;
    if (mobile) el.dataset.mobile = "1";
    else delete (el.dataset as any).mobile;
    if (noai) el.dataset.noai = "1";
    else delete (el.dataset as any).noai;
  } catch {
    // ignore
  }
}

export function postMobileLessonCompleteOnce(lessonId?: string) {
  try {
    if (typeof window === "undefined") return;
    const { mobile, lid } = getMobileParamsFromUrl();
    if (!mobile) return;

    const finalLessonId = lessonId ?? lid;
    const w = window as any;
    if (!w.ReactNativeWebView || typeof w.ReactNativeWebView.postMessage !== "function") return;

    // single-shot guard (per page load)
    if (!w.__RN_LESSON_COMPLETE_SENT__) w.__RN_LESSON_COMPLETE_SENT__ = {};
    const key = finalLessonId ?? "__unknown__";
    if (w.__RN_LESSON_COMPLETE_SENT__[key]) return;
    w.__RN_LESSON_COMPLETE_SENT__[key] = true;

    w.ReactNativeWebView.postMessage(JSON.stringify({ type: "lessonComplete", lessonId: finalLessonId }));
  } catch {
    // ignore
  }
}



import Link from "next/link";
import { ChevronLeft, Map, Puzzle } from "lucide-react";

export default function LearnMenuPage() {
  return (
    <div className="home-root" style={{ background: "#f6f1e6" }}>
      <header className="home-header">
        <div className="home-header-inner">
          <Link
            href="/"
            className="flex items-center gap-2 font-semibold text-[#3a2b17]"
            style={{ textDecoration: "none" }}
          >
            <ChevronLeft className="w-5 h-5" />
            戻る
          </Link>

          <div className="home-logo">
            <span className="home-logo-main">特訓</span>
          </div>

          <div style={{ width: 80 }} />
        </div>
      </header>

      <main className="home-main">
        <div className="home-shell">
          <h1 className="home-page-title" style={{ textAlign: "center" }}>
            特訓メニュー
          </h1>

          <section className="home-training" style={{ marginTop: 0 }}>
            <div className="home-training-header" style={{ justifyContent: "center" }}>
              <div className="home-training-accent" />
              <div className="home-training-title">選んで開始</div>
            </div>

            <div className="home-training-grid home-training-grid--2">
              <Link href="/learn/roadmap" className="training-card training-card--learn">
                <div className="training-card-icon">
                  <Map className="w-6 h-6" />
                </div>
                <div>
                  <div className="training-card-title">ロードマップ</div>
                  <div className="training-card-sub">Duolingo風レッスンで基礎から学ぶ</div>
                </div>
              </Link>

              <Link href="/learn/tsume" className="training-card training-card--review">
                <div className="training-card-icon">
                  <Puzzle className="w-6 h-6" />
                </div>
                <div>
                  <div className="training-card-title">詰将棋</div>
                  <div className="training-card-sub">短手数から鍛える（解答→チェック）</div>
                </div>
              </Link>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

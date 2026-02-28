import Link from "next/link";
import { Swords, Map, BookOpenCheck } from "lucide-react";

const trainingCards = [
  {
    href: "/play",
    title: "実践対局",
    description: "AIや道場メンバーとの真剣勝負",
    icon: Swords,
    modifier: "training-card--play",
    iconColor: "#1b3b5f",
  },
  {
    href: "/learn",
    title: "特訓",
    description: "弱点テーマを集中的に攻略",
    icon: Map,
    modifier: "training-card--learn",
    iconColor: "#4b7b34",
  },
  {
    href: "/annotate",
    title: "復習",
    description: "棋譜をアップロードしてAIと振り返り",
    icon: BookOpenCheck,
    modifier: "training-card--review",
    iconColor: "#b43a32",
  },
];

export default function HomePage() {
  return (
    <div className="home-root home-root--no-header">
      <main className="home-main">
        <div className="home-shell">
          <h1 className="home-page-title">将棋学習サイト</h1>
          <div className="home-training-grid">
            {trainingCards.map((card) => (
              <Link key={card.title} href={card.href} className={`training-card ${card.modifier}`}>
                <div className="training-card-icon">
                  <card.icon size={24} color={card.iconColor} />
                </div>
                <div>
                  <div className="training-card-title">{card.title}</div>
                  <div className="training-card-sub">{card.description}</div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}

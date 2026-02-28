// src/lib/gameState.ts
import { sfenToPlaced, type Placed } from "./sfen";

export interface GameState {
  board: Placed[];
  ply: number;
}

/**
 * 初期局面からUSI手順を指定手数まで実行して盤面を取得
 * 簡易実装：実際の駒の移動は行わず、エンジンAPIに問い合わせて結果のSFENを取得
 */
export async function getGameStateAtPly(moves: string[], ply: number): Promise<GameState> {
  // 指定手数までの手順を取得
  const movesToPlay = moves.slice(0, ply);
  
  // USI形式で組み立て
  const usi = movesToPlay.length > 0 
    ? `startpos moves ${movesToPlay.join(" ")}`
    : "startpos";

  try {
    // エンジンAPIを使って盤面のSFENを取得
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"}/engine/position`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usi })
    });

    if (!response.ok) {
      throw new Error(`Engine API error: ${response.status}`);
    }

    const result = await response.json();
    const sfen = result.sfen || "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1";
    
    return {
      board: sfenToPlaced(sfen),
      ply
    };
  } catch (error) {
    console.warn("Engine API not available, falling back to initial position:", error);
    // フォールバック：エンジンAPIが利用できない場合は初期局面を返す
    return {
      board: sfenToPlaced("startpos"),
      ply
    };
  }
}

/**
 * キャッシュ付きの盤面状態取得
 */
const stateCache = new Map<string, GameState>();

export async function getCachedGameStateAtPly(moves: string[], ply: number): Promise<GameState> {
  const cacheKey = `${moves.slice(0, ply).join(",")}_${ply}`;
  
  if (stateCache.has(cacheKey)) {
    return stateCache.get(cacheKey)!;
  }

  const state = await getGameStateAtPly(moves, ply);
  stateCache.set(cacheKey, state);
  
  // キャッシュサイズ制限（100局面まで）
  if (stateCache.size > 100) {
    const firstKey = stateCache.keys().next().value;
    if (firstKey) {
      stateCache.delete(firstKey);
    }
  }
  
  return state;
}
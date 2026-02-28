"use client";
import React, { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Board } from "@/components/Board";
import type { Placed, PieceCode } from "@/lib/sfen";
import { sfenToPlaced } from "@/lib/sfen";
import { fetchWithAuth } from "@/lib/fetchWithAuth";

type Side = "black" | "white";
type Hand = Record<"P"|"L"|"N"|"S"|"G"|"B"|"R", number>;
type PieceBase = keyof Hand;

const START_BOARD: Placed[] = sfenToPlaced("startpos");

function clonePieces(p: Placed[]): Placed[] { return p.map(x => ({ piece: x.piece, x: x.x, y: x.y })); }
function isBlackPiece(pc: PieceCode): boolean { return pc[0] === "+" ? pc[1] === pc[1].toUpperCase() : pc === (pc as string).toUpperCase(); }
function demotePieceBase(code: PieceCode): PieceBase | null {
  const c = code.startsWith("+") ? code[1] : code[0];
  const up = c.toUpperCase();
  if ((["P","L","N","S","G","B","R"] as const).includes(up as PieceBase)) return up as PieceBase;
  if (up === "K") return null; // 王は持ち駒にならない
  return null;
}
function coordsToUsi(x: number, y: number): string { const file = 9 - x; const rank = String.fromCharCode("a".charCodeAt(0) + y); return `${file}${rank}`; }
function canPromoteBase(b: string): boolean { return ["P","L","N","S","B","R"].includes(b.toUpperCase()); }
// function inPromoZone(side: Side, y: number): boolean { return side === "black" ? y <= 2 : y >= 6; }

type BestmoveOverlay = { from: {x:number;y:number}; to: {x:number;y:number} } | null;

type HandViewProps = {
  side: Side;
  hands: { black: Hand; white: Hand };
  turn: Side;
  handSel: { side: Side; piece: keyof Hand } | null;
  onSelectHand: (side: Side, piece: keyof Hand) => void;
};

function HandView({ side, hands, turn, handSel, onSelectHand }: HandViewProps) {
  const H = hands[side];
  const order: (keyof Hand)[] = ["R","B","G","S","N","L","P"];
  return (
    <div className="flex flex-wrap gap-2">
      {order.map(k => (
        <button key={k}
          className={`
            px-3 py-2 rounded-lg border text-sm font-bold transition-all
            ${handSel && handSel.side===side && handSel.piece===k 
              ? 'bg-amber-300 text-[#3a2b17] border-amber-500 shadow-md scale-[1.02]' 
              : 'bg-white border-black/10 text-slate-700 hover:bg-amber-50'}
            disabled:opacity-40 disabled:cursor-not-allowed
          `}
          onClick={() => onSelectHand(side, k)}
          disabled={(H[k]||0)===0 || turn!==side}
          title={`${side==='black'?'先手':'後手'}の持駒 ${k}`}
        >
          <span className="mr-1">{k}</span>
          <span className="text-xs opacity-70">x{H[k]||0}</span>
        </button>
      ))}
    </div>
  );
}

export default function LocalPlay() {
  const [pieces, setPieces] = useState<Placed[]>(() => clonePieces(START_BOARD));
  const [turn, setTurn] = useState<Side>("black");
  const [hands, setHands] = useState<{black: Hand; white: Hand}>(() => ({ black: {P:0,L:0,N:0,S:0,G:0,B:0,R:0}, white: {P:0,L:0,N:0,S:0,G:0,B:0,R:0} }));
  const [moves, setMoves] = useState<string[]>([]);
  const [fromSel, setFromSel] = useState<{x:number;y:number}|null>(null);
  const [handSel, setHandSel] = useState<{side:Side; piece: keyof Hand} | null>(null);
  const [promote, setPromote] = useState(false);

  const sideLabel = turn === "black" ? "先手" : "後手";

  function resetAll() {
    setPieces(clonePieces(START_BOARD));
    setHands({ black: {P:0,L:0,N:0,S:0,G:0,B:0,R:0}, white: {P:0,L:0,N:0,S:0,G:0,B:0,R:0} });
    setMoves([]); setFromSel(null); setHandSel(null); setPromote(false); setTurn("black");
  }

  function undo() {
    if (!moves.length) return;
    // 簡易実装: 末尾を削除してリロード...はできないので、とりあえずアラート
    alert("Undo機能は現在実装中です (状態の再構築が必要です)");
  }

  function onBoardClick(x: number, y: number) {
    // 簡易実装: 移動ロジック
    if (handSel) {
      // 持ち駒を打つ
      const move = `${handSel.piece}*${coordsToUsi(x, y)}`;
      setMoves([...moves, move]);
      setHands(prev => ({
        ...prev,
        [turn]: { ...prev[turn], [handSel.piece]: prev[turn][handSel.piece] - 1 }
      }));
      // 盤面に配置
      const code = (turn === "black" ? handSel.piece : handSel.piece.toLowerCase()) as PieceCode;
      setPieces([...pieces, { piece: code, x, y }]);
      
      setHandSel(null);
      setTurn(turn === "black" ? "white" : "black");
      return;
    }

    if (fromSel) {
      // 盤上の駒を動かす
      const from = fromSel;
      const to = {x, y};
      // 自分の駒をクリックしたら選択変更
      const targetSelf = pieces.find(p => p.x === x && p.y === y && isBlackPiece(p.piece) === (turn === "black"));
      if (targetSelf) {
        setFromSel({x, y});
        return;
      }

      const move = `${coordsToUsi(from.x, from.y)}${coordsToUsi(to.x, to.y)}${promote ? "+" : ""}`;
      setMoves([...moves, move]);
      
      // 盤面更新
      setPieces(prev => {
        const next = prev.filter(p => !(p.x === from.x && p.y === from.y)); // 元の駒を削除
        const captured = prev.find(p => p.x === x && p.y === y); // 取られる駒
        if (captured) {
          // 持ち駒に追加
          const base = demotePieceBase(captured.piece);
          if (base) {
            setHands(h => ({
              ...h,
              [turn]: { ...h[turn], [base]: h[turn][base] + 1 }
            }));
          }
        }
        // 移動先の駒を追加 (簡易的に元の駒を置く。成りの処理は省略)
        const source = prev.find(p => p.x === from.x && p.y === from.y);
        if (source) {
            // 成り判定
            const isPromoted = promote; 
            let newPiece = source.piece;
            if (isPromoted) {
                newPiece = (turn === "black" ? "+" + source.piece : "+" + source.piece.toLowerCase()) as PieceCode; // 簡易
            }
            next.push({ piece: newPiece, x, y }); // 既存の駒があれば上書き(filterで消えてるはずだがcapturedの処理が必要)
            // capturedはnextから除外する必要がある
            const final = next.filter(p => !(p.x === x && p.y === y));
            final.push({ piece: newPiece, x, y });
            return final;
        }
        return next;
      });

      setFromSel(null);
      setPromote(false);
      setTurn(turn === "black" ? "white" : "black");
    } else {
      // 選択
      const p = pieces.find(p => p.x === x && p.y === y);
      if (p && isBlackPiece(p.piece) === (turn === "black")) {
        setFromSel({x, y});
      }
    }
  }

  function selectHand(side: Side, piece: keyof Hand) {
    if (side !== turn) return;
    if (hands[side][piece] > 0) {
      setHandSel({ side, piece });
      setFromSel(null);
    }
  }
  const boardOverlay = useMemo<BestmoveOverlay>(() => {
    if (!fromSel) return null;
    return { from: {x: fromSel.x, y: fromSel.y}, to: {x: fromSel.x, y: fromSel.y} };
  }, [fromSel]);

  async function callDigest() {
    const usi = moves.length ? `startpos moves ${moves.join(" ")}` : "startpos";
    const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_ENGINE_URL || process.env.ENGINE_URL || "http://localhost:8787";
    const url = `${API_BASE}/digest`;
    // eslint-disable-next-line no-console
    console.log("[web] localplay digest fetch to:", url);
    try {
      const res = await fetchWithAuth(url, {
        method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ usi })
      });
      if (!res.ok) {
        const errText = await res.text();
        console.error(`[web] localplay digest error: ${url} status=${res.status} body=${errText}`);
        alert("ダイジェストAPIエラー: " + errText);
        return;
      }
      const json = await res.json();
      alert((json.summary || []).join("\n"));
    } catch (e) {
      alert("ダイジェストAPI通信エラー: " + String(e));
    }
  }
  async function callAnnotate() {
    const usi = moves.length ? `startpos moves ${moves.join(" ")}` : "startpos";
    const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_ENGINE_URL || process.env.ENGINE_URL || "http://localhost:8787";
    const url = `${API_BASE}/annotate`;
    // eslint-disable-next-line no-console
    console.log("[web] localplay annotate fetch to:", url);
    try {
      const res = await fetchWithAuth(url, {
        method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ usi, byoyomi_ms: 500 })
      });
      if (!res.ok) {
        const errText = await res.text();
        console.error(`[web] localplay annotate error: ${url} status=${res.status} body=${errText}`);
        alert("注釈APIエラー: " + errText);
        return;
      }
      const json = await res.json();
      type NoteView = { ply?: number; move?: string; delta_cp?: number | null };
      const notes: NoteView[] = Array.isArray(json.notes) ? json.notes : [];
      alert("要約:\n" + (json.summary || "") + "\n\n先頭3件:\n" + notes.slice(0,3).map((n)=>`${n.ply}. ${n.move} Δcp:${n.delta_cp??"?"}`).join("\n"));
    } catch (e) {
      alert("注釈API通信エラー: " + String(e));
    }
  }

  return (
    <div className="bg-shogi-panel rounded-3xl p-6 md:p-8 border border-white/5 shadow-xl max-w-5xl mx-auto space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/5 pb-6">
        <h2 className="text-xl font-bold text-[#2b2b2b] flex items-center gap-2">
          <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"/>
          ローカル対局（β）
        </h2>
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="outline" onClick={undo} disabled={!moves.length} className="bg-transparent border-black/10 text-slate-600 hover:bg-black/5 hover:text-[#2b2b2b]">
            一手戻す
          </Button>
          <Button variant="outline" onClick={resetAll} className="bg-transparent border-black/10 text-slate-600 hover:bg-black/5 hover:text-[#2b2b2b]">
            リセット
          </Button>
          <label className="ml-2 text-sm inline-flex items-center gap-2 text-slate-300 cursor-pointer bg-black/20 px-3 py-2 rounded-lg hover:bg-black/30 transition-colors">
            <input 
              type="checkbox" 
              checked={promote} 
              onChange={(e)=>setPromote(e.target.checked)} 
              className="w-4 h-4 rounded border-slate-500 text-shogi-gold focus:ring-shogi-gold bg-transparent"
            /> 
            <span>成り</span>
          </label>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-8">
        <div className="flex flex-col items-center">
          <div className="mb-4 text-sm text-slate-400 bg-black/20 px-4 py-1 rounded-full">
            手番: <span className={`font-bold ${turn === "black" ? "text-[#2b2b2b]" : "text-slate-500"}`}>{sideLabel}</span>
          </div>
          
          {/* Board Wrapper */}
          <div 
            className="relative p-1 rounded-xl bg-gradient-to-br from-amber-800 to-amber-900 shadow-2xl"
            onContextMenu={(e)=>e.preventDefault()} 
            onClick={(e)=>{
              const svg = (e.target as HTMLElement).closest('svg');
              if (!svg) return;
              const rect = (svg as SVGSVGElement).getBoundingClientRect();
              const x = Math.floor(((e.clientX - rect.left) - 10) / 50);
              const y = Math.floor(((e.clientY - rect.top) - 10) / 50);
              if (x>=0 && x<9 && y>=0 && y<9) onBoardClick(x,y);
            }}
          >
            <Board pieces={pieces} bestmove={boardOverlay} />
          </div>
        </div>

        <div className="space-y-6 w-full">
          <div className="bg-black/20 p-4 rounded-2xl border border-white/5">
            <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">先手 (Black)</div>
            <HandView side="black" hands={hands} turn={turn} handSel={handSel} onSelectHand={selectHand} />
          </div>
          
          <div className="bg-black/20 p-4 rounded-2xl border border-white/5">
            <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">後手 (White)</div>
            <HandView side="white" hands={hands} turn={turn} handSel={handSel} onSelectHand={selectHand} />
          </div>

          <div className="pt-4 border-t border-white/5">
            <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">Game Log (USI)</div>
            <div className="font-mono text-xs text-slate-300 bg-black/40 rounded-xl p-4 min-h-[100px] max-h-[200px] overflow-y-auto border border-white/5 leading-relaxed break-all">
              {moves.join(" ") || <span className="text-slate-600 italic">No moves yet...</span>}
            </div>
            
            <div className="grid grid-cols-2 gap-3 mt-4">
              <Button 
                variant="secondary" 
                onClick={callDigest} 
                disabled={!moves.length}
                className="bg-[#fef1d6] hover:bg-[#fde0a2] text-[#2b2b2b] border border-black/10"
              >
                10秒ダイジェスト
              </Button>
              <Button 
                onClick={callAnnotate} 
                disabled={!moves.length}
                className="bg-[#fde7ef] hover:bg-[#fbd1e3] text-[#2b2b2b] border border-black/10"
              >
                注釈を生成
              </Button>
            </div>
          </div>
          
          <div className="text-xs text-slate-600 text-center">
            注意: 現状は合法手判定を厳密には行いません（β版）。
          </div>
        </div>
      </div>
    </div>
  );
}

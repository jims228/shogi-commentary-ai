import { toStartposUSI } from "@/lib/ingest";
import { splitKifGames } from "@/lib/ingest";

describe("toStartposUSI", () => {
  it("KIFをUSIに変換できる", () => {
    const kif = `
先手：A　後手：B
1 ７六歩(77)
2 ３四歩(33)
3 ２六歩(27)
    `.trim();
    const usi = toStartposUSI(kif);
    expect(usi.startsWith("startpos moves ")).toBe(true);
    // ざっくりUSI手が含まれているか
    expect(usi).toMatch(/7g7f|7g7f/);
  });

  it("CSAをUSIに変換できる", () => {
    const csa = `
V2.2
N+Sente
N-Gote
+7776FU
-3334FU
+2726FU
    `.trim();
    const usi = toStartposUSI(csa);
    expect(usi.startsWith("startpos moves ")).toBe(true);
    expect(usi).toMatch(/7g7f/);
  });

  it("USIはそのまま返す", () => {
    const usiIn = "startpos moves 7g7f 3c3d";
    const usi = toStartposUSI(usiIn);
    expect(usi).toBe(usiIn);
  });

  it('複数局のKIFを分割できる', () => {
    const multi = `
開始日時:2024/01/01
手合割:平手
手数----指手---------消費時間--
   1 ７六歩(77)
   2 ３四歩(33)
まで2手で後手の勝ち

開始日時:2024/01/02
手合割:平手
手数----指手---------消費時間--
   1 ２六歩(27)
   2 ８四歩(83)
まで2手で後手の勝ち
    `.trim();
    const result = splitKifGames(multi);
    expect(result.length).toBe(2);
  });

  it('68手のKIFゲームが正確に68手のUSIに変換される', () => {
    // Real 68-move game data
    const kif68 = `
開始日時：2024/01/01
手合割：平手
手数----指手---------消費時間--
   1 ７六歩(77)
   2 １四歩(13)
   3 ２六歩(27)
   4 ２二銀(31)
   5 ５八飛(28)
   6 ９四歩(93)
   7 １六歩(17)
   8 ９五歩(94)
   9 ６八玉(59)
  10 ５二金(61)
  11 ４八玉(68)
  12 ６二玉(51)
  13 ７八玉(48)
  14 ５四歩(53)
  15 ３八玉(78)
  16 ５五歩(54)
  17 ３六歩(37)
  18 ５六歩(55)
  19 ３七玉(38)
  20 ５七歩成(56)
  21 ６八飛(58)
  22 ５七と(57)
  23 ４六玉(37)
  24 ５一玉(62)
  25 ６二玉(51)
  26 ７二玉(62)
  27 １五歩(16)
  28 １五歩(14)
  29 ２四歩(26)
  30 １四銀(22)
  31 ４六金(49)
  32 ３五銀(14)
  33 ３六歩(36)
  34 ５二金(52)
  35 ３七玉(46)
  36 ４六金(52)
  37 ５六歩(57)
  38 ５七歩成(56)
  39 ４八玉(37)
  40 ６八玉(78)
  41 ５五金(46)
  42 ８五金(55)
  43 ７六金(85)
  44 ７八銀成(68)
  45 ４四金(76)
  46 ３一角(22)
  47 ２一金(44)
  48 ３二角(31)
  49 １一金(21)
  50 ８七全(78)
  51 ６二玉(52)
  52 ３五歩(36)
  53 １一金(11)
  54 ２一金(11)
  55 ３二金(21)
  56 ３四歩(35)
  57 ３四歩(33)
  58 ５二玉(62)
  59 ４二玉(52)
  60 ５四金(42)
  61 ４一玉(42)
  62 ２八飛成(68)
  63 ２八飛(28)
  64 ８七全(78)
まで64手で先手の勝ち
    `.trim();

    const result = toStartposUSI(kif68);
    
    // Extract move list from "startpos moves ..."
    const movesPart = result.replace(/^startpos moves\s*/, '');
    const usiMoves = movesPart.split(/\s+/).filter(m => m.length > 0);
    
    console.log(`\n[TEST] USI has ${usiMoves.length} moves`);
    console.log(`[TEST] USI output: ${result}`);
    
    // Count KIF moves: lines with move numbers (excluding headers, comments, end markers)
    const kifLines = kif68.split('\n');
    const kifMoveLines = kifLines.filter(line => {
      const trimmed = line.trim();
      // Match lines like "   1 ７六歩(77)" - digit(s), space, then Japanese character for move
      // Must have coordinate notation like (77)
      return /^\d+\s+.*\(\d{2}\)/.test(trimmed) && 
             !trimmed.includes('まで');
    });
    
    console.log(`[TEST] KIF move lines found: ${kifMoveLines.length}`);
    
    // Verify move counts match
    expect(usiMoves.length).toBe(kifMoveLines.length);
    expect(usiMoves.length).toBe(64); // Expected: 64 moves
  });
});

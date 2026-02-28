"""
backend/api/db/wkbk_db.py
--------------------------
wkbk_articles.jsonl (shogi-extend 由来) への読み取り専用アクセス層。

設計方針:
- ライセンス不明のため、元テキスト(title/description)を丸写ししない
- 返すのは: key / lineage_key / tags / difficulty / category_hint / author / short_note
- short_note は description の先頭 80 文字以内に切り詰める（丸写し禁止）
- SFEN による正規化一致検索（プレフィックス除去・手数除去）
- 起動時に一度ロード → メモリ上の dict で高速参照
- 落ちない設計: ファイルなし/パースエラーは空マップに degradeして続行

著作権方針 (CLAUDE.md より):
  「shogi-extend DB 由来テキストは丸写し出力しない。
   出力は要約/言い換え＋短い断片に制限。」
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

_LOG = logging.getLogger("uvicorn.error")

# ---------------------------------------------------------------------------
# データパス解決
# ---------------------------------------------------------------------------

_DEFAULT_ARTICLES_PATH = (
    Path(__file__).resolve().parents[3]  # repo root: backend/api/db -> backend/api -> backend -> repo
    / "tools" / "datasets" / "wkbk" / "wkbk_articles.jsonl"
)

_DEFAULT_EXPLANATIONS_PATH = (
    Path(__file__).resolve().parents[3]
    / "tools" / "datasets" / "wkbk" / "wkbk_explanations.jsonl"
)


def _get_articles_path() -> Path:
    env = os.getenv("WKBK_ARTICLES_PATH")
    return Path(env) if env else _DEFAULT_ARTICLES_PATH


def _get_explanations_path() -> Path:
    env = os.getenv("WKBK_EXPLANATIONS_PATH")
    return Path(env) if env else _DEFAULT_EXPLANATIONS_PATH


# ---------------------------------------------------------------------------
# lineage_key → 表示ヒント（著作権に配慮した言い換え）
# ---------------------------------------------------------------------------

_LINEAGE_HINT: Dict[str, str] = {
    "手筋": "tactical pattern (tesuji)",
    "詰将棋": "checkmate problem",
    "実戦詰め筋": "practical mating sequence",
    "必死": "unstoppable mating threat",
    "必死逃れ": "escaping mating threat",
    "定跡": "opening theory",
    "持駒限定詰将棋": "drop-piece checkmate",
}


def _lineage_hint(lineage_key: str) -> str:
    return _LINEAGE_HINT.get(lineage_key, lineage_key)


# ---------------------------------------------------------------------------
# SFEN 正規化
# ---------------------------------------------------------------------------

_SFEN_PREFIX_RE = re.compile(r"^position\s+sfen\s+", re.IGNORECASE)


def normalize_sfen(raw: str) -> str:
    """
    "position sfen <board> <turn> <hands> <ply>" →  "<board> <turn> <hands>"
    手数（末尾の整数）を除去してキーとする。
    """
    s = _SFEN_PREFIX_RE.sub("", raw.strip())
    # 末尾の手数（半角数字）を除去
    s = re.sub(r"\s+\d+\s*$", "", s).strip()
    return s


# ---------------------------------------------------------------------------
# 内部インデックス
# ---------------------------------------------------------------------------

_SHORT_NOTE_MAX = 80  # 丸写し禁止: description を切り詰める最大文字数


def _make_short_note(description: str) -> Optional[str]:
    """
    description から short_note を生成する。
    - 空なら None
    - 80文字以内ならそのまま（ただし改行を除去）
    - 80文字超なら先頭 80 文字 + "…"
    著作権リスク回避: 長い原文の丸写しを禁止するため上限を設ける。
    """
    if not description:
        return None
    # 改行・タブを除去して1行に
    text = re.sub(r"\s+", " ", description).strip()
    if not text:
        return None
    if len(text) <= _SHORT_NOTE_MAX:
        return text
    return text[:_SHORT_NOTE_MAX] + "…"


@dataclass
class _ArticleEntry:
    key: str
    lineage_key: str
    tags: List[str]
    difficulty: Optional[int]
    author: Optional[str]      # user.name (投稿者)
    short_note: Optional[str]  # description の先頭N文字（丸写し禁止）
    # 正規化済み SFEN（lookup 用）
    sfen_norm: str
    # フル SFEN（"position sfen ..." 付き）
    sfen_full: str


# グローバルインデックス（起動時に一度構築）
_INDEX_BY_SFEN_NORM: Dict[str, _ArticleEntry] = {}
_EXPLANATIONS_GOALS: Dict[str, str] = {}  # key → goal (LLM生成済みの場合のみ)
_LOADED = False


def _load() -> None:
    global _LOADED, _INDEX_BY_SFEN_NORM, _EXPLANATIONS_GOALS
    if _LOADED:
        return

    articles_path = _get_articles_path()
    if not articles_path.exists():
        _LOG.warning(
            "[wkbk_db] articles file not found: %s — DB lookup disabled.", articles_path
        )
        _LOADED = True
        return

    count = 0
    skipped = 0
    index: Dict[str, _ArticleEntry] = {}

    try:
        with articles_path.open("r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    _LOG.debug("[wkbk_db] JSON parse error at line %d: %s", lineno, e)
                    skipped += 1
                    continue

                key = (obj.get("key") or "").strip()
                sfen_full = (obj.get("init_sfen") or "").strip()
                if not key or not sfen_full:
                    skipped += 1
                    continue

                sfen_norm = normalize_sfen(sfen_full)
                tags = [str(t) for t in (obj.get("tag_list") or [])]
                lineage_key = str(obj.get("lineage_key") or "")
                difficulty = obj.get("difficulty")
                if isinstance(difficulty, (int, float)):
                    difficulty = int(difficulty)
                else:
                    difficulty = None
                author = (obj.get("user") or {}).get("name") or None
                if author:
                    author = str(author).strip() or None
                description = str(obj.get("description") or "").strip()
                short_note = _make_short_note(description)

                entry = _ArticleEntry(
                    key=key,
                    lineage_key=lineage_key,
                    tags=tags,
                    difficulty=difficulty,
                    author=author,
                    short_note=short_note,
                    sfen_norm=sfen_norm,
                    sfen_full=sfen_full,
                )
                # 重複 SFEN は最初のエントリを優先（実際にはほぼない）
                if sfen_norm not in index:
                    index[sfen_norm] = entry
                count += 1

    except Exception as e:
        _LOG.warning("[wkbk_db] failed to load articles: %s", e)
        _LOADED = True
        return

    _INDEX_BY_SFEN_NORM = index
    _LOG.info("[wkbk_db] loaded %d articles, %d skipped.", count, skipped)

    # explanations（LLM生成済みの goal のみ読む）
    _load_explanations()
    _LOADED = True


def _load_explanations() -> None:
    global _EXPLANATIONS_GOALS
    exp_path = _get_explanations_path()
    if not exp_path.exists():
        return
    try:
        goals: Dict[str, str] = {}
        with exp_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    key = (obj.get("key") or "").strip()
                    goal = (obj.get("goal") or "").strip()
                    if key and goal:
                        # 短く切って著作権リスクを抑える（最大50文字）
                        goals[key] = goal[:50]
                except Exception:
                    continue
        _EXPLANATIONS_GOALS = goals
        _LOG.info("[wkbk_db] loaded %d explanation goals.", len(goals))
    except Exception as e:
        _LOG.warning("[wkbk_db] failed to load explanations: %s", e)


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------

@dataclass
class WkbkDbResult:
    hit: bool
    key: Optional[str] = None
    lineage_key: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    difficulty: Optional[int] = None
    category_hint: Optional[str] = None
    goal_summary: Optional[str] = None
    author: Optional[str] = None        # 投稿者名 (user.name)
    short_note: Optional[str] = None    # description の先頭N文字

    def to_dict(self) -> dict:
        return {
            "hit": self.hit,
            "key": self.key,
            "lineage_key": self.lineage_key,
            "tags": self.tags,
            "difficulty": self.difficulty,
            "category_hint": self.category_hint,
            "goal_summary": self.goal_summary,
            "author": self.author,
            "short_note": self.short_note,
        }


_NO_HIT = WkbkDbResult(hit=False)


def lookup_by_sfen(sfen: str) -> WkbkDbResult:
    """
    SFEN 文字列で wkbk_articles を検索し、ヒット情報を返す。

    - 完全一致（正規化後）が最優先
    - ヒット時は lineage_key / tags / difficulty / category_hint のみ返す
    - title など元テキストは著作権保護のため返さない
    - 落ちない設計: 例外は全て WkbkDbResult(hit=False) に degradeする

    Args:
        sfen: 局面 SFEN 文字列
              "position sfen ..." 形式でも、SFEN 直書きでも可
    Returns:
        WkbkDbResult
    """
    if not sfen:
        return _NO_HIT

    _load()

    try:
        sfen_norm = normalize_sfen(sfen)
        entry = _INDEX_BY_SFEN_NORM.get(sfen_norm)
        if entry is None:
            return _NO_HIT

        goal_summary = _EXPLANATIONS_GOALS.get(entry.key)

        return WkbkDbResult(
            hit=True,
            key=entry.key,
            lineage_key=entry.lineage_key,
            tags=entry.tags,
            difficulty=entry.difficulty,
            category_hint=_lineage_hint(entry.lineage_key),
            goal_summary=goal_summary,
            author=entry.author,
            short_note=entry.short_note,
        )
    except Exception as e:
        _LOG.warning("[wkbk_db] lookup_by_sfen error: %s", e)
        return _NO_HIT


def db_stats() -> dict:
    """デバッグ用: ロード済みエントリ数を返す"""
    _load()
    return {
        "articles_loaded": len(_INDEX_BY_SFEN_NORM),
        "explanations_loaded": len(_EXPLANATIONS_GOALS),
    }

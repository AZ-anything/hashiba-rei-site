"""
データ検査（works.json / bl_works.json / youtube.json）

  python validate_works.py

崩れたデータや件数の減少を、コミット前に見つけて止める。問題があれば exit 1。
GitHub Actions では両ワークフローのコミット直前に走るので、引っかかると赤くなり何もコミットされない。

・作品1件ごと: タイトル・サークル名・URL・カバーの崩れ（validate）
・ファイル全体: 同じ作品の重複 / total と実件数の食い違い
・件数: 直前のコミット（HEAD）より減っていたら止める
  2026-07-15、古い手順書に従った上書きで 172件 → 166件 になり、エラーも出ず緑のまま
  8作品が消えた。その再発防止。意図して減らすときは手で直してコミットする（この検査は通らない）
"""

import sys, json, re, subprocess

sys.stdout.reconfigure(encoding="utf-8")

WORK_FILES = ["works.json", "bl_works.json"]
YOUTUBE_FILE = "youtube.json"


def validate(work: dict) -> list:
    """作品1件の崩れを返す。崩れたまま保存すると画面を見るまで気づけないため"""
    problems = []
    title = work.get("title", "")
    if not title:
        problems.append("タイトルが空")
    if "予告作品" in title:
        problems.append("タイトルに「予告作品」が残っている")
    if re.search(r"\[[^\[\]]*\]\s*$", title):
        problems.append("タイトル末尾に [サークル名] が残っている")
    if "﻿" in title:
        problems.append("タイトルに不可視文字(BOM)が入っている")
    if not work.get("circle"):
        problems.append("サークル名が空")
    if not work.get("url"):
        problems.append("URLが空")
    if not work.get("cover"):
        problems.append("カバー画像が空")
    # 画面の stLabel() が知っている値だけ通す
    if work.get("status") not in ("released", "announced", "upcoming", "preorder"):
        problems.append(f"status が不正: {work.get('status')!r}")
    for u in work.get("ended_urls", []):
        if u not in (work.get("url"), work.get("url2")):
            problems.append(f"ended_urls に url / url2 以外が入っている: {u}")
    return problems


def work_key(url: str) -> str:
    m = re.search(r"(RJ\d+|BJ\d+|cid=[a-zA-Z0-9_]+)", url or "")
    return m.group(1) if m else (url or "")


def check_work_file(data: dict) -> list:
    problems = []
    works = data.get("works", [])
    seen = {}
    for w in works:
        label = w.get("title", "")[:30] or w.get("url", "(不明)")
        for p in validate(w):
            problems.append(f"{label}: {p}")
        k = work_key(w.get("url", ""))
        if k in seen:
            problems.append(f"{label}: 重複している（{k}）")
        seen[k] = True
    if data.get("total") != len(works):
        problems.append(f"total({data.get('total')}) と実件数({len(works)}) が食い違っている")
    return problems


def count_items(data: dict) -> int:
    return len(data.get("works", data.get("items", [])))


def previous_count(path: str):
    """直前のコミットの件数。無ければ None（新規ファイルなど）"""
    try:
        out = subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True, check=True)
        return count_items(json.loads(out.stdout.decode("utf-8")))
    except Exception:
        return None


def main():
    failed = False
    for path in WORK_FILES + [YOUTUBE_FILE]:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        problems = check_work_file(data) if path in WORK_FILES else []

        now, before = count_items(data), previous_count(path)
        if before is not None and now < before:
            problems.append(f"件数が減っている: {before}件 → {now}件")

        if problems:
            failed = True
            print(f"❌ {path}")
            for p in problems:
                print(f"  - {p}")
        else:
            print(f"✅ {path}（{now}件）")

    if failed:
        print("データが崩れているためコミットしません。")
        sys.exit(1)


if __name__ == "__main__":
    main()

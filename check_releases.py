"""
announced/upcoming 作品の発売チェック＋発売時期自動更新スクリプト
GitHub Actions から毎日 0:10 JST に実行。

・発売済みになっていたら status を released に更新
・発売予定時期が空の作品はDLsiteから自動取得して補完
"""

import requests, json, re, time
from bs4 import BeautifulSoup
from datetime import datetime, timezone

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


# ─── 発売予定時期の取得 ───────────────────────────────────────

def get_release_period(page_url: str) -> tuple[str, str]:
    """
    DLsite announceページから発売予定時期を取得。
    Returns: (release_period表示文字列, date ISO形式) 取得できない場合は ("", "")
    """
    try:
        r = requests.get(page_url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        for el in soup.find_all(string=re.compile("発売予定時期|発売予定日")):
            nxt = el.parent.find_next_sibling()
            if nxt:
                raw = nxt.get_text(strip=True)
                if raw and raw not in ("未定", ""):
                    return _parse_date_text(raw)

        for th in soup.find_all(["th", "dt"], string=re.compile("発売予定")):
            td = th.find_next_sibling(["td", "dd"])
            if td:
                raw = td.get_text(strip=True)
                if raw and raw not in ("未定", ""):
                    return _parse_date_text(raw)

    except Exception as e:
        print(f"  [発売時期取得エラー] {e}")

    return ("", "")


def _parse_date_text(raw: str) -> tuple[str, str]:
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw)
    if m:
        y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
        return (f"{mo}月{d}日", f"{y}-{str(mo).zfill(2)}-{str(d).zfill(2)}")
    m = re.search(r"(\d{4})年(\d{1,2})月(上旬|中旬|下旬)", raw)
    if m:
        return (f"{int(m.group(2))}月{m.group(3)}", "")
    m = re.search(r"(\d{4})年(\d{1,2})月", raw)
    if m:
        return (f"{int(m.group(2))}月", "")
    return (raw, "")


# ─── 発売チェック ─────────────────────────────────────────────

def extract_product_id(url: str) -> str | None:
    m = re.search(r"/(RJ|BJ)(\d+)\.html", url)
    return f"{m.group(1)}{m.group(2)}" if m else None


def is_released(product_id: str) -> bool:
    for domain in ["girls", "girls-drama"]:
        url = f"https://www.dlsite.com/{domain}/work/=/product_id/{product_id}.html"
        try:
            r = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
            if r.status_code == 200:
                return True
        except Exception:
            continue
    return False


# ─── メイン ──────────────────────────────────────────────────

def main():
    with open("works.json", encoding="utf-8") as f:
        data = json.load(f)

    works   = data["works"]
    pending = [w for w in works if w["status"] in ("announced", "upcoming", "preorder")]
    changed = False
    today   = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"チェック対象: {len(pending)} 件")

    for w in pending:
        pid = extract_product_id(w["url"])
        if not pid:
            continue

        print(f"\n  [{pid}] {w['title'][:35]}")

        # ① 発売チェック
        if is_released(pid):
            print(f"  ✅ 発売済みに変更")
            w["status"]       = "released"
            w["release_date"] = today
            w["date"]         = today
            w["url"]          = f"https://www.dlsite.com/girls/work/=/product_id/{pid}.html"
            changed = True
            time.sleep(1)
            continue

        # ② 発売時期が未設定なら自動取得
        if "/announce/" in w["url"] and not w.get("release_period", ""):
            period, date = get_release_period(w["url"])
            if period:
                print(f"  📅 発売時期を取得: {period}")
                w["release_period"] = period
                changed = True
            if date and not w.get("date", ""):
                w["date"] = date
                changed = True
            if not period:
                print(f"     発売時期：DLsite未記載")

        time.sleep(1)

    if changed:
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        with open("works.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("\n✅ works.json を更新しました")
    else:
        print("\n変更なし。スキップします。")


if __name__ == "__main__":
    main()

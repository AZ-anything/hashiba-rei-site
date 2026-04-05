"""
announced/upcoming 作品の発売チェック＋発売時期自動更新スクリプト
GitHub Actions から毎日 0:10 JST に実行。

・発売済みになっていたら status を released に更新
・発売予定時期が空の作品はDLsiteから自動取得して補完
・発売検知時はDLsiteの販売ページから正確な発売日を取得
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


# ─── 実際の発売日をDLsite販売ページから取得 ──────────────────

def get_actual_release_date(product_id: str) -> str:
    """
    DLsite販売ページの作品概要テーブルから正確な発売日を取得。
    Returns: ISO形式 "YYYY-MM-DD"、取得できなければ ""
    """
    for domain in ["girls", "girls-drama", "maniax"]:
        url = f"https://www.dlsite.com/{domain}/work/=/product_id/{product_id}.html"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            table = soup.find("table", id="work_outline")
            if table:
                for tr in table.find_all("tr"):
                    th = tr.find("th")
                    td = tr.find("td")
                    if th and td and "販売日" in th.text:
                        m = re.search(r"(\d{4})年(\d{2})月(\d{2})日", td.text)
                        if m:
                            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        except Exception as e:
            print(f"  [発売日取得エラー] {domain}: {e}")
        time.sleep(0.5)
    return ""


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
            w["status"] = "released"
            w["url"]    = f"https://www.dlsite.com/girls/work/=/product_id/{pid}.html"

            # DLsiteから正確な発売日を取得（取得できなければ今日の日付をフォールバック）
            actual_date = get_actual_release_date(pid)
            w["date"] = actual_date if actual_date else today
            if actual_date:
                print(f"  📅 発売日取得: {actual_date}")
            else:
                print(f"  📅 発売日取得失敗 → 今日の日付で代替: {today}")

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
        # released作品を発売日新しい順に並び替え
        released_dated   = [w for w in works if w["status"] == "released" and w.get("date")]
        released_undated = [w for w in works if w["status"] == "released" and not w.get("date")]
        announced        = [w for w in works if w["status"] != "released"]
        data["works"] = announced + sorted(released_dated, key=lambda x: x["date"], reverse=True) + released_undated

        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        with open("works.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("\n✅ works.json を更新しました")
    else:
        print("\n変更なし。スキップします。")


if __name__ == "__main__":
    main()

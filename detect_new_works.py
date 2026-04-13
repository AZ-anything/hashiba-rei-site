"""
羽柴礼の新作自動検出スクリプト
GitHub Actions から毎日実行。

・DLsite で「羽柴礼」をキーワード検索
・作品ページの声優欄に名前があることを確認（誤検出防止）
・works.json に未登録の作品を status: "candidate" として仮登録
・Cowork で Az が確認後、正式に announced/released に変更する運用
"""

import requests, json, re, time, sys
from bs4 import BeautifulSoup
from datetime import datetime, timezone

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
VA_NAME = "羽柴礼"
SEARCH_DOMAINS = ["girls", "girls-touch", "girls-drama", "girls-drama-touch"]


# ─── DLsite 検索で候補 product_id を収集 ──────────────────────

def search_dlsite() -> set[str]:
    """DLsite のキーワード検索で product_id を収集する"""
    pids: set[str] = set()

    for domain in SEARCH_DOMAINS:
        for page in range(1, 5):
            url = (
                f"https://www.dlsite.com/{domain}/fsr/=/keyword/"
                f"%E7%BE%BD%E6%9F%B4%E7%A4%BC/per_page/100/page/{page}/show_type/1"
            )
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                r.encoding = "utf-8"
                soup = BeautifulSoup(r.text, "html.parser")
                found = 0
                for a in soup.select("a[href*='/product_id/']"):
                    m = re.search(r"(RJ|BJ)\d+", a.get("href", ""))
                    if m:
                        pids.add(m.group(0))
                        found += 1
                if found == 0:
                    break
            except Exception as e:
                print(f"  [検索エラー] {domain} page {page}: {e}")
                break
            time.sleep(0.5)

    # announce (予告) ページも検索
    for domain in SEARCH_DOMAINS:
        url = (
            f"https://www.dlsite.com/{domain}/fsr/=/keyword/"
            f"%E7%BE%BD%E6%9F%B4%E7%A4%BC/work_type/announce/per_page/100"
        )
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.encoding = "utf-8"
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a[href*='/product_id/']"):
                m = re.search(r"(RJ|BJ)\d+", a.get("href", ""))
                if m:
                    pids.add(m.group(0))
        except Exception as e:
            print(f"  [announce検索エラー] {domain}: {e}")
        time.sleep(0.5)

    return pids


# ─── 作品ページから声優名を確認＋メタ情報を取得 ──────────────

def fetch_work_info(product_id: str) -> dict | None:
    """
    作品ページをスクレイピングし、声優欄に VA_NAME があれば情報を返す。
    なければ None を返す（誤検出フィルタ）。
    """
    # 販売ページと予告ページの両方を試行
    page_types = [
        ("work", "{domain}/work/=/product_id/{pid}.html"),
        ("announce", "{domain}/announce/=/product_id/{pid}.html"),
    ]

    for domain in SEARCH_DOMAINS:
        for ptype, pattern in page_types:
            url = "https://www.dlsite.com/" + pattern.format(domain=domain, pid=product_id)
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
                if r.status_code != 200:
                    continue
                r.encoding = "utf-8"
                soup = BeautifulSoup(r.text, "html.parser")

                # ── 声優欄チェック ──
                va_found = False
                # work_outline テーブル方式
                table = soup.find("table", id="work_outline")
                if table:
                    for tr in table.find_all("tr"):
                        th = tr.find("th")
                        if th and "声優" in th.get_text():
                            td = tr.find("td")
                            if td and VA_NAME in td.get_text():
                                va_found = True
                                break

                # announce ページ方式 (テーブルがない場合)
                if not va_found:
                    for el in soup.find_all(string=re.compile("声優")):
                        parent = el.parent
                        if parent:
                            sib = parent.find_next_sibling()
                            if sib and VA_NAME in sib.get_text():
                                va_found = True
                                break
                    # ページ全体のテキストでもフォールバック確認
                    if not va_found:
                        page_text = soup.get_text()
                        # 声優セクション周辺に名前があるか
                        if VA_NAME in page_text:
                            # より厳密に: 声優/CV の近くにあるか
                            for pattern_str in [r"声優.*?" + VA_NAME, r"CV.*?" + VA_NAME, VA_NAME + r".*?声優"]:
                                if re.search(pattern_str, page_text, re.DOTALL):
                                    va_found = True
                                    break

                if not va_found:
                    continue

                # ── メタ情報取得 ──
                title = ""
                title_el = soup.find("h1", id="work_name") or soup.find("h1")
                if title_el:
                    # a タグ内のテキストを優先
                    a = title_el.find("a")
                    title = (a or title_el).get_text(strip=True)

                circle = ""
                circle_el = soup.find("span", class_="maker_name")
                if circle_el:
                    a = circle_el.find("a")
                    circle = (a or circle_el).get_text(strip=True)

                cover = ""
                # OGP画像
                og = soup.find("meta", property="og:image")
                if og:
                    cover = og.get("content", "")

                status = "announced" if ptype == "announce" else "released"

                return {
                    "title": title,
                    "circle": circle,
                    "url": url,
                    "cover": cover,
                    "date": "",
                    "status": status,
                    "release_period": "",
                    "genres": [],
                    "_candidate": True,  # 候補フラグ
                }

            except Exception as e:
                print(f"  [取得エラー] {url}: {e}")
            time.sleep(0.5)

    return None


# ─── メイン ──────────────────────────────────────────────────

def main():
    with open("works.json", encoding="utf-8") as f:
        data = json.load(f)

    # 既存の product_id 一覧
    existing_ids = set()
    for w in data["works"]:
        m = re.search(r"(RJ|BJ)\d+", w["url"])
        if m:
            existing_ids.add(m.group(0))

    print(f"既存作品数: {len(existing_ids)}")

    # DLsite 検索
    print("DLsite を検索中...")
    found_ids = search_dlsite()
    print(f"検索結果: {len(found_ids)} 件")

    new_ids = found_ids - existing_ids
    # 既に candidate として登録済みのものも除外
    candidate_ids = set()
    for w in data["works"]:
        if w.get("_candidate"):
            m = re.search(r"(RJ|BJ)\d+", w["url"])
            if m:
                candidate_ids.add(m.group(0))
    new_ids -= candidate_ids

    if not new_ids:
        print("新作は見つかりませんでした。")
        return

    print(f"\n未登録作品: {len(new_ids)} 件 → 声優確認中...")

    added = 0
    for pid in sorted(new_ids):
        print(f"\n  [{pid}] 確認中...")
        info = fetch_work_info(pid)
        if info:
            print(f"  ✅ {info['title']} ({info['circle']}) → candidate として追加")
            data["works"].insert(0, info)
            added += 1
        else:
            print(f"  ❌ 声優欄に「{VA_NAME}」なし → スキップ")
        time.sleep(1)

    if added > 0:
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        with open("works.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n✅ {added} 件を candidate として works.json に追加しました")
    else:
        print("\n声優確認を通過した新作はありませんでした。")


if __name__ == "__main__":
    main()

"""
announced/upcoming 作品の発売チェック＋発売時期・価格・レビュー自動更新スクリプト
GitHub Actions から毎日 0:10 JST に実行。

対象ファイル:
  ・works.json     … 乙女向け（羽柴礼名義 / DLsite girls / DMM digital_doujin_tl）
  ・bl_works.json  … BL（羽柴令名義 / DLsite bl / DMM digital_doujin_bl）

各ファイルに対して:
  ・発売済みになっていたら status を released に更新
  ・発売予定時期が空の作品はDLsiteから自動取得して補完
  ・発売検知時はDLsiteから正確な発売日・ジャンルを取得
  ・らぶカル作品（lovecul.dmm.co.jp）はDMMアフィリエイトAPIで発売チェック
  ・released作品の価格・レビュー件数を最新化
"""

import os, requests, json, re, time
from bs4 import BeautifulSoup
from datetime import datetime, timezone

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ─── 対象ファイルごとの設定（乙女向け / BL）──────────────────
CONFIGS = [
    {
        "file": "works.json",
        "label": "乙女向け",
        "domains": ["girls", "girls-drama", "girls-touch", "girls-drama-touch", "maniax"],
        "section": "girls",
        "dmm_floor": "digital_doujin_tl",
        "keyword": "羽柴礼",
        "fsr_section": "girls",
    },
    {
        "file": "bl_works.json",
        "label": "BL",
        "domains": ["bl"],
        "section": "bl",
        "dmm_floor": "digital_doujin_bl",
        "keyword": "羽柴令",
        "fsr_section": "bl",
    },
]


# ─── らぶカル（DMMアフィリエイトAPI） ─────────────────────────

def extract_cid(url: str):
    m = re.search(r"cid=([a-zA-Z0-9_]+)", url)
    return m.group(1) if m else None


def dmm_api_lookup(cid: str, floor: str):
    """DMMアフィリエイトAPIで作品情報を取得。未掲載（予告段階）ならNone"""
    api_id = os.environ.get("DMM_API_ID", "")
    aff_id = os.environ.get("DMM_AFFILIATE_ID", "")
    if not api_id or not aff_id:
        print("  ⚠️ DMM_API_ID / DMM_AFFILIATE_ID が未設定（らぶカルチェックをスキップ）")
        return None
    try:
        r = requests.get("https://api.dmm.com/affiliate/v3/ItemList", params={
            "api_id": api_id, "affiliate_id": aff_id,
            "site": "FANZA", "service": "doujin", "floor": floor,
            "cid": cid, "output": "json",
        }, timeout=15)
        items = r.json().get("result", {}).get("items", [])
        return items[0] if items else None
    except Exception as e:
        print(f"  [DMM APIエラー] {e}")
        return None


def check_lovecul(w: dict, today: str, floor: str) -> bool:
    """らぶカル作品の発売チェック。変更があればTrue"""
    cid = extract_cid(w["url"])
    if not cid:
        return False
    item = dmm_api_lookup(cid, floor)
    if not item:
        print("     DMM API未掲載（予告段階）")
        return False

    date_str = item.get("date", "")[:10].replace("/", "-")
    if date_str and date_str <= today:
        print(f"  ✅ 発売済みに変更（らぶカル）")
        w["status"] = "released"
        w["date"] = date_str
        m = re.match(r"\d{4}-(\d{2})-(\d{2})", date_str)
        if m:
            w["release_period"] = f"{int(m.group(1))}月{int(m.group(2))}日"
        genres = [g["name"] for g in item.get("iteminfo", {}).get("genre", [])]
        if genres:
            w["genres"] = genres
        img = item.get("imageURL", {}).get("large", "")
        if img:
            w["cover"] = img
        print(f"  📅 発売日: {date_str} / 🏷️ ジャンル: {genres}")
        return True
    return False


# ─── 発売予定時期の取得 ───────────────────────────────────────

def get_release_period(page_url: str):
    """DLsite announceページから発売予定時期を取得。(表示文字列, dateISO) or ("","")"""
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


def _parse_date_text(raw: str):
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


# ─── 実際の発売日・ジャンルをDLsiteから取得 ──────────────────

def get_actual_release_date(product_id: str, domains: list):
    """
    product.json（確実）→ 失敗時 work_outline の順で発売日・ジャンルを取得。
    Returns: ("YYYY-MM-DD", [genres]) / ("", [])
    """
    for domain in domains:
        # ① product.json（新作でもJS非依存で取得可）
        try:
            r = requests.get(
                f"https://www.dlsite.com/{domain}/api/=/product.json?workno={product_id}",
                headers=HEADERS, timeout=15)
            if r.status_code == 200:
                arr = r.json()
                if arr:
                    d = arr[0]
                    rd = (d.get("regist_date") or "")[:10]
                    genres = [g.get("name") for g in (d.get("genres") or []) if g.get("name")]
                    if rd:
                        return (rd, genres)
        except Exception as e:
            print(f"  [product.json取得エラー] {domain}: {e}")
        # ② work_outline テーブル（フォールバック）
        try:
            url = f"https://www.dlsite.com/{domain}/work/=/product_id/{product_id}.html"
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "lxml")
                table = soup.find("table", id="work_outline")
                date_str = ""; genres = []
                if table:
                    for tr in table.find_all("tr"):
                        th = tr.find("th"); td = tr.find("td")
                        if not th or not td:
                            continue
                        if "販売日" in th.text:
                            m = re.search(r"(\d{4})年(\d{2})月(\d{2})日", td.text)
                            if m:
                                date_str = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
                        if "ジャンル" in th.text:
                            genres = [a.text.strip() for a in td.find_all("a")]
                if date_str:
                    return (date_str, genres)
        except Exception as e:
            print(f"  [発売日取得エラー] {domain}: {e}")
        time.sleep(0.5)
    return ("", [])


# ─── 発売チェック ─────────────────────────────────────────────

def extract_product_id(url: str):
    m = re.search(r"/(RJ|BJ)(\d+)\.html", url)
    return f"{m.group(1)}{m.group(2)}" if m else None


def is_released(product_id: str, domains: list) -> bool:
    for domain in domains:
        url = f"https://www.dlsite.com/{domain}/work/=/product_id/{product_id}.html"
        try:
            r = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
            if r.status_code == 200:
                return True
        except Exception:
            continue
    return False


# ─── 価格・レビューの日次更新 ─────────────────────────────────

def _yen(t):
    m = re.search(r"([\d,]+)", t or "")
    return int(m.group(1).replace(",", "")) if m else None


def fetch_dlsite_prices(fsr_section: str, keyword: str) -> dict:
    """DLsite 名義検索から RJ→{price,list_price,review_count} を取得"""
    out = {}
    kw = requests.utils.quote(keyword)
    for page in [1, 2]:
        url = (f"https://www.dlsite.com/{fsr_section}/fsr/=/keyword/{kw}"
               f"/work_category%5B0%5D/doujin/per_page/100/page/{page}/")
        try:
            r = requests.get(url, headers=HEADERS, timeout=25); r.encoding = "utf-8"
            soup = BeautifulSoup(r.text, "lxml")
            for a in soup.select("a[href*='/product_id/RJ']"):
                li = a.find_parent("li") or a.find_parent("tr")
                if not li:
                    continue
                m = re.search(r"product_id/(RJ\d+)", a["href"])
                if not m or m.group(1) in out:
                    continue
                pr = li.select_one(".work_price")
                if not pr:
                    continue
                price = _yen(pr.get_text())
                st = li.select_one(".strike")
                lp = _yen(st.get_text()) if st else price
                wr = li.select_one(".work_review")
                rc = 0
                if wr:
                    mm = re.search(r"(\d+)", wr.get_text())
                    rc = int(mm.group(1)) if mm else 0
                out[m.group(1)] = {"price": price, "list_price": lp, "review_count": rc}
        except Exception as e:
            print(f"  [DLsite価格取得エラー] {e}")
        time.sleep(0.5)
    return out


def fetch_dmm_prices(floor: str, keyword: str) -> dict:
    """DMM 名義検索から cid→{price,list_price,review_count} を取得"""
    out = {}
    api_id = os.environ.get("DMM_API_ID", ""); aff = os.environ.get("DMM_AFFILIATE_ID", "")
    if not api_id or not aff:
        return out
    try:
        r = requests.get("https://api.dmm.com/affiliate/v3/ItemList", params={
            "api_id": api_id, "affiliate_id": aff, "site": "FANZA", "service": "doujin",
            "floor": floor, "keyword": keyword, "hits": 100, "output": "json"}, timeout=15)
        for x in r.json().get("result", {}).get("items", []):
            p = x.get("prices", {}); rv = x.get("review", {})
            out[x["content_id"]] = {
                "price": int(p["price"]) if str(p.get("price", "")).isdigit() else None,
                "list_price": int(p["list_price"]) if str(p.get("list_price", "")).isdigit() else None,
                "review_count": rv.get("count", 0)}
    except Exception as e:
        print(f"  [DMM価格取得エラー] {e}")
    return out


def update_prices_reviews(works: list, cfg: dict) -> bool:
    """全released作品の価格・レビューを最新化。変更があればTrue"""
    dl = fetch_dlsite_prices(cfg["fsr_section"], cfg["keyword"])
    dmm = fetch_dmm_prices(cfg["dmm_floor"], cfg["keyword"])
    if not dl and not dmm:
        print("  価格データ取得できず（スキップ）")
        return False
    changed = False
    for w in works:
        if w.get("status") != "released":
            continue
        u, u2 = w.get("url", ""), w.get("url2", "")
        rjm = re.search(r"product_id/(RJ\d+)", u) or re.search(r"product_id/(RJ\d+)", u2)
        cidm = re.search(r"cid=(\w+)", u) or re.search(r"cid=(\w+)", u2)
        rj = rjm.group(1) if rjm else None
        cid = cidm.group(1) if cidm else None
        np = nlp = None
        if "dlsite" in u and rj in dl:
            np = dl[rj]["price"]; nlp = dl[rj]["list_price"]
        elif cid in dmm:
            np = dmm[cid]["price"]; nlp = dmm[cid]["list_price"]
        counts = []
        if rj in dl: counts.append(dl[rj]["review_count"])
        if cid in dmm: counts.append(dmm[cid]["review_count"])
        nrc = max(counts) if counts else 0
        if np is not None and (w.get("price") != np or w.get("list_price") != nlp):
            w["price"] = np; w["list_price"] = nlp
            w["on_sale"] = bool(nlp and np < nlp); changed = True
        if w.get("review_count") != nrc:
            w["review_count"] = nrc; changed = True
    return changed


# ─── 1ファイルの処理 ─────────────────────────────────────────

def process_file(cfg: dict):
    path = cfg["file"]
    if not os.path.exists(path):
        print(f"\n==== {cfg['label']}（{path}）: ファイルなし、スキップ ====")
        return
    print(f"\n==== {cfg['label']}（{path}）の発売チェック ====")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    works = data["works"]
    pending = [w for w in works if w["status"] in ("announced", "upcoming", "preorder")]
    changed = False
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"チェック対象: {len(pending)} 件")

    for w in pending:
        if "lovecul.dmm.co.jp" in w["url"]:
            print(f"\n  [らぶカル {extract_cid(w['url'])}] {w['title'][:35]}")
            if check_lovecul(w, today, cfg["dmm_floor"]):
                changed = True
            time.sleep(1)
            continue

        pid = extract_product_id(w["url"])
        if not pid:
            continue
        print(f"\n  [{pid}] {w['title'][:35]}")

        if is_released(pid, cfg["domains"]):
            print(f"  ✅ 発売済みに変更")
            w["status"] = "released"
            w["url"] = f"https://www.dlsite.com/{cfg['section']}/work/=/product_id/{pid}.html"
            actual_date, genres = get_actual_release_date(pid, cfg["domains"])
            w["date"] = actual_date if actual_date else today
            w["genres"] = genres
            w["release_period"] = ""
            print(f"  📅 発売日: {w['date']}  🏷️ ジャンル: {genres}")
            changed = True
            time.sleep(1)
            continue

        if "/announce/" in w["url"]:
            old_period = w.get("release_period", "")
            old_date = w.get("date", "")
            period, date = get_release_period(w["url"])
            if not old_period and period:
                print(f"  📅 発売時期を取得: {period}")
                w["release_period"] = period; changed = True
            elif old_period and period and period != old_period:
                print(f"  📅 発売時期が更新: {old_period} → {period}")
                w["release_period"] = period; changed = True
            if date and date != old_date:
                print(f"  📅 発売日が確定: {date}")
                w["date"] = date; changed = True
            elif not period and not old_period:
                print(f"     発売時期：DLsite未記載")
        time.sleep(1)

    print("\n💰 価格・レビュー更新中...")
    if update_prices_reviews(works, cfg):
        changed = True
        print("  価格・レビューを更新しました")

    if changed:
        released_dated = [w for w in works if w["status"] == "released" and w.get("date")]
        released_undated = [w for w in works if w["status"] == "released" and not w.get("date")]
        announced = [w for w in works if w["status"] != "released"]
        data["works"] = announced + sorted(released_dated, key=lambda x: x["date"], reverse=True) + released_undated
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n✅ {path} を更新しました")
    else:
        print(f"\n変更なし（{path}）。スキップします。")


def main():
    for cfg in CONFIGS:
        process_file(cfg)


if __name__ == "__main__":
    main()

"""
作品追加スクリプト（DLsite / らぶカル 両対応）
GitHub Actions の workflow_dispatch から URL を渡して実行する。

  python add_work.py <作品URL>

・DLsite (dlsite.com): 販売ページ/告知ページからタイトル・サークル・カバー・発売日・ジャンルを取得
・らぶカル (lovecul.dmm.co.jp): 作品詳細ページから同粒度の情報を取得
・works.json に追加（URL重複チェックあり）して保存
・取得したHTMLは fetched_page.html に保存される（パーサ調整用にartifactへ）
"""

import sys, json, re, time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
COOKIES = {"age_check_done": "1", "ckcy": "1", "cklg": "ja"}  # DMM系年齢確認スキップ


def fetch(url: str) -> str:
    r = requests.get(url, headers=HEADERS, cookies=COOKIES, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    with open("fetched_page.html", "w", encoding="utf-8") as f:
        f.write(r.text)
    return r.text


def date_to_period(iso: str) -> str:
    m = re.match(r"\d{4}-(\d{2})-(\d{2})", iso)
    return f"{int(m.group(1))}月{int(m.group(2))}日" if m else ""


# ─── DLsite ──────────────────────────────────────────────────

DLSITE_DOMAINS = ["girls", "girls-drama", "girls-touch", "girls-drama-touch", "maniax"]


def parse_dlsite(url: str) -> dict:
    m = re.search(r"product_id/((?:RJ|BJ)\d+)", url)
    if not m:
        raise ValueError(f"product_idが抽出できません: {url}")
    pid = m.group(1)

    # 販売ページ優先で探索
    for domain in DLSITE_DOMAINS:
        wurl = f"https://www.dlsite.com/{domain}/work/=/product_id/{pid}.html"
        try:
            r = requests.get(wurl, headers=HEADERS, timeout=15)
        except Exception:
            continue
        if r.status_code != 200:
            time.sleep(0.5)
            continue
        r.encoding = "utf-8"
        with open("fetched_page.html", "w", encoding="utf-8") as f:
            f.write(r.text)
        soup = BeautifulSoup(r.text, "lxml")
        work = _dlsite_common(soup, f"https://www.dlsite.com/girls/work/=/product_id/{pid}.html")
        date_str, genres = "", []
        table = soup.find("table", id="work_outline")
        if table:
            for tr in table.find_all("tr"):
                th, td = tr.find("th"), tr.find("td")
                if not th or not td:
                    continue
                if "販売日" in th.text:
                    dm = re.search(r"(\d{4})年(\d{2})月(\d{2})日", td.text)
                    if dm:
                        date_str = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
                if "ジャンル" in th.text:
                    genres = [a.text.strip() for a in td.find_all("a")]
        work.update(date=date_str, status="released", genres=genres,
                    release_period=date_to_period(date_str))
        return work

    # 告知ページ
    for domain in DLSITE_DOMAINS:
        aurl = f"https://www.dlsite.com/{domain}/announce/=/product_id/{pid}.html"
        try:
            r = requests.get(aurl, headers=HEADERS, timeout=15)
        except Exception:
            continue
        if r.status_code != 200:
            time.sleep(0.5)
            continue
        r.encoding = "utf-8"
        with open("fetched_page.html", "w", encoding="utf-8") as f:
            f.write(r.text)
        soup = BeautifulSoup(r.text, "lxml")
        work = _dlsite_common(soup, f"https://www.dlsite.com/girls/announce/=/product_id/{pid}.html")
        period, date = "", ""
        for el in soup.find_all(string=re.compile("発売予定時期|発売予定日")):
            nxt = el.parent.find_next_sibling()
            if nxt:
                raw = nxt.get_text(strip=True)
                if raw and raw != "未定":
                    period, date = _parse_date_text(raw)
                    break
        work.update(date=date, status="announced", genres=[], release_period=period)
        return work

    raise ValueError(f"DLsiteで {pid} のページが見つかりません")


def _dlsite_common(soup, url) -> dict:
    og_title = soup.find("meta", property="og:title")
    og_image = soup.find("meta", property="og:image")
    title, circle = "", ""
    if og_title:
        tm = re.match(r"^(.*?)\s*\[(.*?)\]\s*\|", og_title["content"])
        if tm:
            title, circle = tm.group(1).strip(), tm.group(2).strip()
        else:
            title = og_title["content"].split("|")[0].strip()
    return {
        "title": title, "circle": circle, "url": url,
        "cover": og_image["content"] if og_image else "",
    }


def _parse_date_text(raw: str):
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw)
    if m:
        return (f"{int(m.group(2))}月{int(m.group(3))}日",
                f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}")
    m = re.search(r"(\d{4})年(\d{1,2})月(上旬|中旬|下旬)", raw)
    if m:
        return (f"{int(m.group(2))}月{m.group(3)}", "")
    m = re.search(r"(\d{4})年(\d{1,2})月", raw)
    if m:
        return (f"{int(m.group(2))}月", "")
    return (raw, "")


# ─── らぶカル ────────────────────────────────────────────────

def parse_lovecul(url: str) -> dict:
    m = re.search(r"cid=([a-zA-Z0-9_]+)", url)
    if not m:
        raise ValueError(f"cidが抽出できません: {url}")
    cid = m.group(1)
    canonical = f"https://lovecul.dmm.co.jp/tl/-/detail/=/cid={cid}/"

    html = fetch(url)
    soup = BeautifulSoup(html, "lxml")

    work = {"title": "", "circle": "", "url": canonical, "cover": "",
            "date": "", "status": "released", "release_period": "", "genres": []}

    # ① JSON-LD
    for sc in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(sc.string or "")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for d in items:
            if not isinstance(d, dict):
                continue
            if d.get("@type") in ("Product", "CreativeWork", "Book"):
                work["title"] = work["title"] or d.get("name", "")
                img = d.get("image", "")
                work["cover"] = work["cover"] or (img[0] if isinstance(img, list) else img)
                brand = d.get("brand", {})
                if isinstance(brand, dict):
                    work["circle"] = work["circle"] or brand.get("name", "")
                rd = d.get("releaseDate", "") or d.get("datePublished", "")
                if rd:
                    work["date"] = work["date"] or rd[:10]

    # ② Next.js / Nuxt 埋め込みJSONから探索
    state_script = soup.find("script", id="__NEXT_DATA__")
    if state_script and state_script.string:
        try:
            state = json.loads(state_script.string)
            _walk_state(state, work)
        except Exception:
            pass

    # ③ メタタグ fallback
    if not work["title"]:
        og = soup.find("meta", property="og:title")
        if og:
            work["title"] = re.sub(r"\s*[\|｜-]\s*らぶカル.*$", "", og["content"]).strip()
    if not work["cover"]:
        og = soup.find("meta", property="og:image")
        if og:
            work["cover"] = og["content"]

    # ④ DOM探索（dt/dd, th/td）
    for label, key in [("サークル", "circle"), ("ブランド", "circle"), ("メーカー", "circle"),
                       ("配信開始日", "date"), ("発売日", "date"), ("商品発売日", "date")]:
        if work[key]:
            continue
        for el in soup.find_all(["th", "dt", "span", "div"], string=re.compile(label)):
            sib = el.find_next_sibling()
            if sib:
                raw = sib.get_text(strip=True)
                if key == "date":
                    dm = re.search(r"(\d{4})[/年.-](\d{1,2})[/月.-](\d{1,2})", raw)
                    if dm:
                        work["date"] = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
                        break
                else:
                    if raw:
                        work[key] = raw
                        break

    # ⑤ ジャンル（ジャンル/タグへのリンク）
    if not work["genres"]:
        genres = []
        for a in soup.find_all("a", href=re.compile(r"(genre|keyword|article)")):
            t = a.get_text(strip=True)
            if t and len(t) <= 12 and t not in genres:
                genres.append(t)
        work["genres"] = genres[:15]

    if work["date"]:
        work["release_period"] = date_to_period(work["date"])
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        work["status"] = "released" if work["date"] <= today else "announced"

    if not work["title"]:
        raise ValueError("らぶカルページからタイトルを取得できませんでした（fetched_page.htmlを確認）")
    return work


def _walk_state(node, work, depth=0):
    """埋め込みJSONを再帰探索して該当キーを拾う"""
    if depth > 12:
        return
    if isinstance(node, dict):
        for k, v in node.items():
            kl = k.lower()
            if isinstance(v, str) and v:
                if not work["title"] and kl in ("title", "productname", "contentname"):
                    work["title"] = v
                elif not work["circle"] and kl in ("makername", "circlename", "brandname", "authorname"):
                    work["circle"] = v
                elif not work["date"] and kl in ("deliverystartdate", "releasedate", "salesstartdate", "begin"):
                    dm = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", v)
                    if dm:
                        work["date"] = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
                elif not work["cover"] and kl in ("packageimageurl", "mainimage", "packageurl") and v.startswith("http"):
                    work["cover"] = v
            else:
                _walk_state(v, work, depth + 1)
    elif isinstance(node, list):
        for v in node:
            _walk_state(v, work, depth + 1)


# ─── メイン ──────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("usage: python add_work.py <URL>")
        sys.exit(1)
    url = sys.argv[1].strip()

    if "dlsite.com" in url:
        work = parse_dlsite(url)
    elif "lovecul.dmm.co.jp" in url:
        work = parse_lovecul(url)
    else:
        raise ValueError(f"未対応のURLです: {url}")

    print("取得結果:")
    print(json.dumps(work, ensure_ascii=False, indent=2))

    with open("works.json", encoding="utf-8") as f:
        data = json.load(f)
    works = data["works"]

    # 重複チェック（URL / product_id / cid）
    key = re.search(r"(RJ\d+|BJ\d+|cid=[a-zA-Z0-9_]+)", work["url"])
    key = key.group(1) if key else work["url"]
    for w in works:
        if key in w["url"]:
            print(f"⚠️ 既に登録済みのためスキップ: {w['title']}")
            sys.exit(0)

    works.append(work)

    # announced先頭・released日付降順（check_releases.pyと同じ規則）
    released_dated   = [w for w in works if w["status"] == "released" and w.get("date")]
    released_undated = [w for w in works if w["status"] == "released" and not w.get("date")]
    announced        = [w for w in works if w["status"] != "released"]
    data["works"] = announced + sorted(released_dated, key=lambda x: x["date"], reverse=True) + released_undated
    data["total"] = len(data["works"])
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    with open("works.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ works.json に追加しました（計 {data['total']} 件）")


if __name__ == "__main__":
    main()

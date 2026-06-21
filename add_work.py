"""
作品追加スクリプト（DLsite / らぶカル 両対応・乙女向け/BL自動振り分け）
GitHub Actions の workflow_dispatch から URL を渡して実行する。

  python add_work.py <作品URL>

・URLから乙女向け / BL を自動判別して追加先ファイルを切り替える:
    - DLsite      … /bl/ を含む → bl_works.json（BL・羽柴令） / それ以外 → works.json（乙女向け・羽柴礼）
    - らぶカル    … /bl/ を含む → bl_works.json（floor=digital_doujin_bl） / それ以外 → works.json（floor=digital_doujin_tl）
・DLsite: product.json で発売日・ジャンル・価格を、og:metaでタイトル・サークル・カバーを取得
・らぶカル: DMMアフィリエイトAPI（ページ直接取得は海外IPブロックのため不可。要 DMM_API_ID / DMM_AFFILIATE_ID）
・追加先JSONに重複チェックの上で追記して保存
"""

import os, sys, json, re, time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

GIRLS_DOMAINS = ["girls", "girls-drama", "girls-touch", "girls-drama-touch", "maniax"]


def date_to_period(iso: str) -> str:
    m = re.match(r"\d{4}-(\d{2})-(\d{2})", iso)
    return f"{int(m.group(1))}月{int(m.group(2))}日" if m else ""


# ─── DLsite ──────────────────────────────────────────────────

def _dlsite_product_json(pid: str, domains: list) -> dict:
    """product.json から date/genres/price を取得（新作でもJS非依存）"""
    for domain in domains:
        try:
            r = requests.get(
                f"https://www.dlsite.com/{domain}/api/=/product.json?workno={pid}",
                headers=HEADERS, timeout=15)
            if r.status_code == 200:
                arr = r.json()
                if arr:
                    d = arr[0]
                    date_str = (d.get("regist_date") or "")[:10]
                    genres = [g.get("name") for g in (d.get("genres") or []) if g.get("name")]
                    price = d.get("price")
                    lp = d.get("official_price") or price
                    return {
                        "date": date_str, "genres": genres,
                        "price": price if isinstance(price, int) else None,
                        "list_price": lp if isinstance(lp, int) else None,
                    }
        except Exception as e:
            print(f"  [product.json取得エラー] {domain}: {e}")
        time.sleep(0.3)
    return {}


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
    return {"title": title, "circle": circle, "url": url,
            "cover": og_image["content"] if og_image else ""}


def parse_dlsite(url: str, domains: list, section: str) -> dict:
    m = re.search(r"product_id/((?:RJ|BJ)\d+)", url)
    if not m:
        raise ValueError(f"product_idが抽出できません: {url}")
    pid = m.group(1)

    # 販売ページ優先
    for domain in domains:
        wurl = f"https://www.dlsite.com/{domain}/work/=/product_id/{pid}.html"
        try:
            r = requests.get(wurl, headers=HEADERS, timeout=15)
        except Exception:
            continue
        if r.status_code != 200:
            time.sleep(0.5)
            continue
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "lxml")
        work = _dlsite_common(soup, f"https://www.dlsite.com/{section}/work/=/product_id/{pid}.html")
        pj = _dlsite_product_json(pid, domains)
        date_str = pj.get("date", "")
        genres = pj.get("genres", [])
        # work_outline フォールバック
        if not date_str or not genres:
            table = soup.find("table", id="work_outline")
            if table:
                for tr in table.find_all("tr"):
                    th, td = tr.find("th"), tr.find("td")
                    if not th or not td:
                        continue
                    if not date_str and "販売日" in th.text:
                        dm = re.search(r"(\d{4})年(\d{2})月(\d{2})日", td.text)
                        if dm:
                            date_str = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
                    if not genres and "ジャンル" in th.text:
                        genres = [a.text.strip() for a in td.find_all("a")]
        price = pj.get("price"); lp = pj.get("list_price")
        work.update(date=date_str, status="released", genres=genres,
                    release_period="", price=price, list_price=lp,
                    on_sale=bool(lp and price and price < lp), review_count=0)
        return work

    # 告知ページ
    for domain in domains:
        aurl = f"https://www.dlsite.com/{domain}/announce/=/product_id/{pid}.html"
        try:
            r = requests.get(aurl, headers=HEADERS, timeout=15)
        except Exception:
            continue
        if r.status_code != 200:
            time.sleep(0.5)
            continue
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "lxml")
        work = _dlsite_common(soup, f"https://www.dlsite.com/{section}/announce/=/product_id/{pid}.html")
        period, date = "", ""
        for el in soup.find_all(string=re.compile("発売予定時期|発売予定日")):
            nxt = el.parent.find_next_sibling()
            if nxt:
                raw = nxt.get_text(strip=True)
                if raw and raw != "未定":
                    period, date = _parse_date_text(raw)
                    break
        work.update(date=date, status="announced", genres=[], release_period=period,
                    review_count=0)
        return work

    raise ValueError(f"DLsiteで {pid} のページが見つかりません")


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


# ─── らぶカル（DMMアフィリエイトAPI） ─────────────────────────

def parse_lovecul(url: str, floor: str, section: str) -> dict:
    m = re.search(r"cid=([a-zA-Z0-9_]+)", url)
    if not m:
        raise ValueError(f"cidが抽出できません: {url}")
    cid = m.group(1)
    canonical = f"https://lovecul.dmm.co.jp/{section}/-/detail/=/cid={cid}/"

    api_id = os.environ.get("DMM_API_ID", "")
    aff_id = os.environ.get("DMM_AFFILIATE_ID", "")
    if not api_id or not aff_id:
        raise ValueError("DMM_API_ID / DMM_AFFILIATE_ID が未設定です（GitHub Secretsに登録してください）")

    r = requests.get("https://api.dmm.com/affiliate/v3/ItemList", params={
        "api_id": api_id, "affiliate_id": aff_id,
        "site": "FANZA", "service": "doujin", "floor": floor,
        "cid": cid, "output": "json",
    }, timeout=15)
    items = r.json().get("result", {}).get("items", [])
    if not items:
        raise ValueError(
            f"DMM APIに {cid} が未掲載です（発売前の予告段階の可能性）。"
            "タイトル・サークル名・発売予定日をチャットで教えてください。")
    item = items[0]

    date_str = item.get("date", "")[:10].replace("/", "-")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    genres = [g["name"] for g in item.get("iteminfo", {}).get("genre", [])]
    makers = item.get("iteminfo", {}).get("maker", [])
    p = item.get("prices", {}); rv = item.get("review", {})
    price = int(p["price"]) if str(p.get("price", "")).isdigit() else None
    lp = int(p["list_price"]) if str(p.get("list_price", "")).isdigit() else price

    return {
        "title": item.get("title", ""),
        "circle": makers[0]["name"] if makers else "",
        "url": canonical,
        "cover": item.get("imageURL", {}).get("large", ""),
        "date": date_str,
        "status": "released" if (date_str and date_str <= today) else "announced",
        "release_period": date_to_period(date_str),
        "genres": genres,
        "price": price, "list_price": lp,
        "on_sale": bool(lp and price and price < lp),
        "review_count": rv.get("count", 0),
    }


# ─── メイン ──────────────────────────────────────────────────

def route(url: str):
    """URLから (parse結果, 追加先ファイル, ラベル) を決める"""
    is_bl = "/bl/" in url
    if "dlsite.com" in url:
        if is_bl:
            return parse_dlsite(url, ["bl"], "bl"), "bl_works.json", "BL"
        return parse_dlsite(url, GIRLS_DOMAINS, "girls"), "works.json", "乙女向け"
    if "lovecul.dmm.co.jp" in url:
        if is_bl:
            return parse_lovecul(url, "digital_doujin_bl", "bl"), "bl_works.json", "BL"
        return parse_lovecul(url, "digital_doujin_tl", "tl"), "works.json", "乙女向け"
    raise ValueError(f"未対応のURLです: {url}")


def main():
    if len(sys.argv) < 2:
        print("usage: python add_work.py <URL>")
        sys.exit(1)
    url = sys.argv[1].strip()

    work, target, label = route(url)
    print(f"判別: {label} → {target}")
    print("取得結果:")
    print(json.dumps(work, ensure_ascii=False, indent=2))

    with open(target, encoding="utf-8") as f:
        data = json.load(f)
    works = data["works"]

    key = re.search(r"(RJ\d+|BJ\d+|cid=[a-zA-Z0-9_]+)", work["url"])
    key = key.group(1) if key else work["url"]
    for w in works:
        if key in w.get("url", "") or key in w.get("url2", ""):
            print(f"⚠️ 既に登録済みのためスキップ: {w['title']}")
            sys.exit(0)

    works.append(work)

    released_dated   = [w for w in works if w["status"] == "released" and w.get("date")]
    released_undated = [w for w in works if w["status"] == "released" and not w.get("date")]
    announced        = [w for w in works if w["status"] != "released"]
    data["works"] = announced + sorted(released_dated, key=lambda x: x["date"], reverse=True) + released_undated
    data["total"] = len(data["works"])
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    with open(target, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ {target} に追加しました（計 {data['total']} 件・{label}）")


if __name__ == "__main__":
    main()

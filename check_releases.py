"""
announced/upcoming 作品の発売チェックスクリプト
GitHub Actions から毎日実行。
発売済みになっていたら works.json を更新してコミット。
"""

import requests, json, re, time
from datetime import datetime, timezone

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def is_released(product_id: str) -> bool:
    """DLsiteの /work/ URLが存在すれば発売済み"""
    # girls / girls-drama 両方を確認
    for domain in ["girls", "girls-drama"]:
        url = f"https://www.dlsite.com/{domain}/work/=/product_id/{product_id}.html"
        try:
            r = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
            if r.status_code == 200:
                return True
        except Exception:
            continue
    return False

def extract_product_id(url: str) -> str | None:
    m = re.search(r'/(RJ|BJ)(\d+)\.html', url)
    return f"{m.group(1)}{m.group(2)}" if m else None

def main():
    with open("works.json", encoding="utf-8") as f:
        data = json.load(f)

    works    = data["works"]
    pending  = [w for w in works if w["status"] in ("announced", "upcoming", "preorder")]
    changed  = False
    today    = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"チェック対象: {len(pending)} 件")

    for w in pending:
        pid = extract_product_id(w["url"])
        if not pid:
            continue
        print(f"  確認中: {w['title'][:40]} ({pid})")
        if is_released(pid):
            print(f"  ✅ 発売済みに変更: {w['title'][:40]}")
            w["status"]       = "released"
            w["release_date"] = today  # ここから30日間PIKUCUPに表示
            # URLを /work/ に更新
            w["url"] = f"https://www.dlsite.com/girls/work/=/product_id/{pid}.html"
            changed = True
        time.sleep(1)

    if changed:
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        with open("works.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("✅ works.json を更新しました")
    else:
        print("変更なし。スキップします。")

if __name__ == "__main__":
    main()

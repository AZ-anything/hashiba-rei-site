"""
YouTube動画取得・マージスクリプト
GitHub Actions から毎日実行し、youtube.json を更新する。

・YouTube Data API v3 で最新動画を取得
・既存の youtube.json とマージ（新規動画のみ追加）
・members_only フラグ等の手動設定データを保持
"""
import requests, json, os, re
from datetime import datetime, timezone

KEY = os.environ["YOUTUBE_API_KEY"]
CH  = "UCn3tBA3UvmDtB_0LyKEG-hA"


# --- 既存データ読み込み ---

existing = {}
try:
    with open("youtube.json", encoding="utf-8") as f:
        data = json.load(f)
    for item in data.get("items", []):
        existing[item["id"]] = item
    print(f"existing: {len(existing)} items")
except FileNotFoundError:
    print("no existing data")


# --- YouTube API で最新動画を取得 ---

def classify_tab(title):
    if re.search(r"歌ってみた|歌って みた", title):
        return "utatte"
    if re.search(r"#[Ss]horts|#ショート", title):
        return "shorts"
    if re.search(r"配信|雑談|ライブ|LIVE", title):
        return "lives"
    return "videos"


r = requests.get(
    "https://www.googleapis.com/youtube/v3/search",
    params={"key": KEY, "channelId": CH, "part": "snippet",
            "order": "date", "maxResults": 50, "type": "video"},
    timeout=15
)
d = r.json()

if "error" in d:
    print(f"API error: {d['error']['message']}")
    exit(1)

new_count = 0
for item in d.get("items", []):
    vid = item["id"]["videoId"]
    title = item["snippet"]["title"]
    published = item["snippet"]["publishedAt"][:10]
    thumbnail = item["snippet"]["thumbnails"].get("medium", {}).get("url", "")

    if vid in existing:
        existing[vid]["title"] = title
        if thumbnail:
            existing[vid]["thumbnail"] = thumbnail
    else:
        existing[vid] = {
            "id": vid,
            "title": title,
            "published": published,
            "thumbnail": thumbnail or "https://i.ytimg.com/vi/" + vid + "/mqdefault.jpg",
            "link": "https://www.youtube.com/watch?v=" + vid,
            "tab": classify_tab(title),
        }
        new_count += 1
        print(f"  NEW: {title[:40]}")


# --- ソートして書き出し ---

items = sorted(existing.values(), key=lambda x: x.get("published", "") or "0000", reverse=True)

output = {
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "items": items
}
with open("youtube.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

tabs = {}
members = 0
for i in items:
    t = i["tab"]
    tabs[t] = tabs.get(t, 0) + 1
    if i.get("members_only"):
        members += 1

vid_c = tabs.get("videos", 0)
uta_c = tabs.get("utatte", 0)
liv_c = tabs.get("lives", 0)
sho_c = tabs.get("shorts", 0)
print(f"\nSaved {len(items)} items (new: {new_count})")
print(f"  videos:{vid_c} / utatte:{uta_c} / lives:{liv_c} / shorts:{sho_c}")
if members:
    print(f"  members-only: {members} (preserved)")

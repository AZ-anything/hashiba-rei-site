"""
YouTube最新動画取得スクリプト
GitHub Actions から毎日実行し、youtube.json を更新します
"""
import requests, json, os, re
from datetime import datetime, timezone

KEY = os.environ["YOUTUBE_API_KEY"]
CH  = "UCn3tBA3UvmDtB_0LyKEG-hA"

r = requests.get(
    "https://www.googleapis.com/youtube/v3/search",
    params={"key": KEY, "channelId": CH, "part": "snippet",
            "order": "date", "maxResults": 50, "type": "video"},
    timeout=15
)
d = r.json()

if "error" in d:
    print(f"❌ API エラー: {d['error']['message']}")
    exit(1)

items = []
for item in d.get("items", []):
    t = item["snippet"]["title"]
    if   re.search(r"歌ってみた|歌って みた", t):       tab = "utatte"
    elif re.search(r"#[Ss]horts|#ショート",       t):       tab = "shorts"
    elif re.search(r"配信|雑談|ライブ|LIVE",  t): tab = "lives"
    else:                                          tab = "videos"

    items.append({
        "id":        item["id"]["videoId"],
        "title":     t,
        "published": item["snippet"]["publishedAt"],
        "thumbnail": item["snippet"]["thumbnails"].get("medium", {}).get("url", ""),
        "link":      f"https://www.youtube.com/watch?v={item['id']['videoId']}",
        "tab":       tab,
    })

output = {
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "items": items
}
with open("youtube.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"✅ {len(items)}件保存（動画:{sum(1 for i in items if i['tab']=='videos')} / ライブ:{sum(1 for i in items if i['tab']=='lives')} / ショート:{sum(1 for i in items if i['tab']=='shorts')}）")

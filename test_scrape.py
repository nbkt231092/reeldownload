import requests, re, json
cookies_dict = {}
try:
    with open('www.facebook.com_cookies.txt', 'r') as f:
        for line in f:
            if not line.startswith('#') and line.strip():
                parts = line.strip().split('\t')
                if len(parts) >= 7:
                    cookies_dict[parts[5]] = parts[6]
except Exception as e:
    print("No cookie:", e)

url = 'https://www.facebook.com/reel/1090159782522778'
r = requests.get(url, cookies=cookies_dict, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9'
})
html = r.text
print('HTML Length:', len(html))

# Try to find LD+JSON
ld_matches = re.findall(r'<script type="application/ld\+json" nonce=".*?">(.*?)</script>', html, re.IGNORECASE)
if ld_matches:
    for ld in ld_matches:
        try:
            data = json.loads(ld)
            print("LD JSON:", json.dumps(data, indent=2))
        except:
            pass

# Try to find other metadata
title_match = re.search(r'<title>(.*?)</title>', html)
if title_match: print("Title tag:", title_match.group(1))

# Search for reaction count
reaction_match = re.search(r'"reaction_count":\s*\{\s*"count":\s*(\d+)', html)
if reaction_match: print("Reaction Count:", reaction_match.group(1))

comment_match = re.search(r'"comment_count":\s*\{\s*"total_count":\s*(\d+)', html)
if comment_match: print("Comment Count:", comment_match.group(1))

view_match = re.search(r'"video_view_count":\s*(\d+)', html)
if view_match: print("View Count:", view_match.group(1))

# Extract caption (often in a meta description or og:description)
meta_desc = re.search(r'<meta name="description" content="(.*?)"', html)
if meta_desc: print("Meta description:", meta_desc.group(1))

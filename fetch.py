#!/usr/bin/env python3
import re, json, os, sys
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
SITE = "https://demyurge.itch.io/dragongame"
want = os.environ.get("WANT", "apk").lower()

s = requests.Session()
s.headers.update({"User-Agent": UA,
                  "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                  "Accept-Language": "en-US,en;q=0.9"})

r = s.get(SITE, timeout=90)
print("PAGE", r.status_code, len(r.content), flush=True)
html = r.text
open("page.html", "w", encoding="utf-8", errors="ignore").write(html)

csrf = None
for pat in (r'name="csrf_token"\s+(?:value|content)="([^"]+)"', r'"csrf_token"\s*:\s*"([^"]+)"'):
    m = re.search(pat, html)
    if m:
        csrf = m.group(1); break
print("CSRF", repr(csrf), flush=True)

# 精确解析: 每个 upload 块 -> (upload_id, 文件名)
uploads = []
for m in re.finditer(r'data-upload_id="(\d+)"', html):
    uid = m.group(1)
    tail = html[m.start(): m.start()+2500]
    stop = tail.find('data-upload_id="', 10)
    if stop > 0:
        tail = tail[:stop]
    fn = re.search(r'href="/file/' + uid + r'[^"]*"[^>]*>\s*([^<]+?)\s*</a>', tail)
    size = re.search(r'file_size[^>]*>\s*<span>([^<]+)</span>', tail)
    name = fn.group(1).strip() if fn else None
    if not name:
        cand = re.findall(r'([A-Za-z0-9][A-Za-z0-9._\-]{3,}\.(?:apk|zip|dmg|exe|ipa))', tail)
        name = cand[0] if cand else None
    uploads.append({"id": uid, "name": name, "size": size.group(1) if size else None})
print("UPLOADS", json.dumps(uploads, ensure_ascii=False), flush=True)

picked = None
for u in uploads:
    if u["name"] and u["name"].lower().endswith("." + want):
        picked = u; break
if not picked:
    print("NO_MATCH", want, flush=True); sys.exit(1)
print("PICKED", json.dumps(picked, ensure_ascii=False), flush=True)

url = "%s/file/%s?source=game_download" % (SITE, picked["id"])
rr = s.post(url, data={"csrf_token": csrf} if csrf else {},
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": SITE,
                     "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
            timeout=90, allow_redirects=False)
print("POST", rr.status_code, rr.text[:200].replace("\n", " "), flush=True)
dl = rr.json()["url"]

fn = re.sub(r'[^A-Za-z0-9._\-]', '_', picked["name"])
print("DOWNLOAD", fn, flush=True)
with s.get(dl, stream=True, timeout=180) as resp:
    resp.raise_for_status()
    total = int(resp.headers.get("Content-Length") or 0)
    got = 0; nxt = 50 << 20
    with open(fn, "wb") as f:
        for chunk in resp.iter_content(1 << 20):
            if not chunk: continue
            f.write(chunk); got += len(chunk)
            if got >= nxt:
                print("  %.1f/%.1f MB" % (got/1e6, total/1e6 if total else 0), flush=True)
                nxt += 50 << 20
print("SAVED", fn, os.path.getsize(fn), flush=True)

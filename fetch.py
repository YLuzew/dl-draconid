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

ids = []
for m in re.finditer(r'data-upload_id="(\d+)"', html):
    if m.group(1) not in ids:
        ids.append(m.group(1))
print("IDS", ids, flush=True)

names = {}
for uid in ids:
    i = html.find('data-upload_id="%s"' % uid)
    seg = html[max(0, i-600): i+1600]
    fn = re.findall(r'([A-Za-z0-9][A-Za-z0-9._\-]{3,}\.(?:apk|zip|dmg|exe|ipa))', seg)
    names[uid] = sorted(set(fn))
print("NAMES", json.dumps(names, ensure_ascii=False), flush=True)

results = []
for uid in ids:
    url = "%s/file/%s?source=game_download" % (SITE, uid)
    try:
        rr = s.post(url,
                    data={"csrf_token": csrf} if csrf else {},
                    headers={"X-Requested-With": "XMLHttpRequest", "Referer": SITE,
                             "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
                    timeout=90, allow_redirects=False)
        print("POST", uid, rr.status_code, rr.text[:300].replace("\n", " "), flush=True)
        try:
            j = rr.json()
        except Exception:
            continue
        u = j.get("url")
        if u:
            results.append((uid, u))
    except Exception as e:
        print("ERR", uid, e, flush=True)

print("URLS", json.dumps(results, ensure_ascii=False), flush=True)
open("urls.json", "w").write(json.dumps(results))

picked = None
for uid, u in results:
    if want in u.lower():
        picked = (uid, u); break
if not picked:
    for uid, u in results:
        if any(n.lower().endswith("." + want) for n in names.get(uid, [])):
            picked = (uid, u); break
if not picked and results:
    picked = results[0]

if not picked:
    print("NO_URL_FOUND", flush=True); sys.exit(1)

uid, u = picked
fn = u.split("?")[0].rstrip("/").split("/")[-1] or ("file-%s.%s" % (uid, want))
fn = re.sub(r'[^A-Za-z0-9._\-]', '_', fn)
print("DOWNLOAD", fn, flush=True)
with s.get(u, stream=True, timeout=180) as resp:
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
open("saved.txt", "w").write(fn)

#!/usr/bin/env python3
"""
Genereert een spoilervrije pagina met NOS WK 2026-samenvattingen.

Draait in GitHub Actions (open netwerk):
- haalt de nieuwste video's van het YouTube-kanaal NOS Sport op (RSS),
- filtert op WK 2026-toernooisamenvattingen,
- STRIPT elke uitslag/score uit de titel (alleen neutrale landnamen blijven over),
- bewaart alles in matches.json (historie groeit aan),
- schrijft index.html, gegroepeerd per wedstrijddag (Amerikaanse tijd).

Het script is robuust: lukt het ophalen niet (bijv. geen netwerk), dan
wordt index.html gewoon opnieuw gebouwd uit de bestaande matches.json.
"""
import json, os, re, sys, html, datetime, urllib.request
from zoneinfo import ZoneInfo

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HANDLE = "nossport"
FALLBACK_CHANNEL_ID = "UC5xziMuoFAOpX9mwUVhe2Jw"
TOURNAMENT_START = datetime.date(2026, 6, 10)
MATCHES_FILE = "matches.json"
OUT_FILE = "index.html"

# Wedstrijddagen worden gegroepeerd op Amerikaanse tijd (VS-oostkust).
US_TZ = ZoneInfo("America/New_York")

DAYS_ABBR = ["ma", "di", "wo", "do", "vr", "za", "zo"]
NL_DAYS_FULL = ["maandag", "dinsdag", "woensdag", "donderdag",
                "vrijdag", "zaterdag", "zondag"]
MONTHS = ["", "januari", "februari", "maart", "april", "mei", "juni",
          "juli", "augustus", "september", "oktober", "november", "december"]


def fetch(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "nl-NL,nl;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def resolve_channel_id():
    try:
        page = fetch(f"https://www.youtube.com/@{HANDLE}/videos")
        for pat in (r'"channelId":"(UC[\w-]{22})"',
                    r'"externalId":"(UC[\w-]{22})"'):
            m = re.search(pat, page)
            if m:
                return m.group(1)
    except Exception as e:
        print("Kon channel-id niet bepalen:", e, file=sys.stderr)
    return FALLBACK_CHANNEL_ID


def fetch_feed_entries(cid):
    xml = fetch(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}")
    out = []
    for block in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
        vid = re.search(r"<yt:videoId>([^<]+)</yt:videoId>", block)
        title = re.search(r"<title>([^<]*)</title>", block)
        pub = re.search(r"<published>([^<]+)</published>", block)
        if vid and title:
            out.append({
                "id": vid.group(1),
                "title": html.unescape(title.group(1)),
                "published": pub.group(1) if pub else "",
            })
    return out


def parse_date(iso):
    try:
        return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return None


def fmt_date(iso):
    d = parse_date(iso)
    if not d:
        return ""
    return f"{DAYS_ABBR[d.weekday()]} {d.day} {MONTHS[d.month]} {d.year}"


def us_matchday(iso):
    """Geeft (sorteersleutel, label) voor de wedstrijddag in VS-oostkusttijd."""
    d = parse_date(iso)
    if not d:
        return ("0000-00-00", "Onbekende dag")
    du = d.astimezone(US_TZ)
    key = du.strftime("%Y-%m-%d")
    label = f"{NL_DAYS_FULL[du.weekday()]} {du.day} {MONTHS[du.month]}"
    return (key, label)


def clean_name(s):
    s = re.sub(r"[^A-Za-zÀ-ÿ .'\-]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .-'")


def neutral_teams(title):
    """Haal 'Land A - Land B' uit de titel en verwijder elke score."""
    # verwijder scores zoals 2-0, 2 - 0, 2:0 en losse cijfers
    t = re.sub(r"\d+\s*[-–:]\s*\d+", " ", title)
    t = re.sub(r"\d", " ", t)
    # verwijder het label 'samenvatting' (incl. ':') zodat het niet in de naam belandt
    t = re.sub(r"(?i)samenvatting[:\s]*", " ", t)
    for seg in re.split(r"[|•·»]", t):
        m = re.search(
            r"([A-ZÀ-Ý][A-Za-zÀ-ÿ.'\-]*(?: [A-Za-zÀ-ÿ.'\-]+)*?)"
            r"\s+[-–]\s+"
            r"([A-ZÀ-Ý][A-Za-zÀ-ÿ.'\-]*(?: [A-Za-zÀ-ÿ.'\-]+)*)",
            seg)
        if m:
            a, b = clean_name(m.group(1)), clean_name(m.group(2))
            if a and b and len(a) <= 30 and len(b) <= 30:
                return f"{a} – {b}"
    return None


def is_wk_samenvatting(e):
    t = e["title"].lower()
    if "samenvatting" not in t:
        return False
    if "kwalificatie" in t or "qualif" in t:
        return False
    d = parse_date(e["published"])
    if d and d.date() < TOURNAMENT_START:
        return False
    return True


def load_matches():
    if os.path.exists(MATCHES_FILE):
        try:
            with open(MATCHES_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_matches(matches):
    with open(MATCHES_FILE, "w", encoding="utf-8") as f:
        json.dump(matches, f, ensure_ascii=False, indent=2)


def update_matches(matches):
    known = {m["id"] for m in matches}
    cid = resolve_channel_id()
    try:
        entries = fetch_feed_entries(cid)
    except Exception as e:
        print("Kon feed niet ophalen, gebruik bestaande matches:", e,
              file=sys.stderr)
        return matches
    added = 0
    for e in entries:
        if e["id"] in known or not is_wk_samenvatting(e):
            continue
        teams = neutral_teams(e["title"])
        if not teams:
            continue  # liever overslaan dan een mogelijke spoiler tonen
        matches.append({
            "id": e["id"],
            "teams": teams,
            "date": fmt_date(e["published"]),
            "published": e["published"],
        })
        known.add(e["id"])
        added += 1
    print(f"{added} nieuwe samenvatting(en) toegevoegd.")
    matches.sort(key=lambda m: m.get("published", ""), reverse=True)
    return matches


PAGE_TEMPLATE = r"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NOS WK 2026 — Samenvattingen (spoilervrij)</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; background:#f5f6f8; color:#15181c; }
  .wrap { max-width:1100px; margin:0 auto; padding:24px 18px 48px; }
  h1 { font-size:22px; margin:0 0 4px; }
  .sub { color:#5b6470; font-size:14px; margin:0; }
  .spoiler-note { display:inline-flex; align-items:center; gap:7px; background:#e8f0ff; color:#1d4ed8; border:1px solid #cdddff; padding:6px 12px; border-radius:999px; font-size:13px; font-weight:500; margin-top:12px; }
  .grid { display:grid; gap:18px; margin-top:10px; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); }
  .dayhead { margin:30px 0 0; padding-bottom:8px; border-bottom:1px solid #e3e6ea; font-size:16px; font-weight:700; display:flex; align-items:baseline; gap:8px; }
  .dayhead .tz { font-size:12px; font-weight:600; color:#8a93a0; }
  #days > .daygroup:first-child .dayhead { margin-top:18px; }
  .card { background:#fff; border:1px solid #e3e6ea; border-radius:14px; overflow:hidden; box-shadow:0 1px 2px rgba(0,0,0,.04); }
  .player { position:relative; width:100%; aspect-ratio:16/9; background:#0b0d10; }
  .cover { position:absolute; inset:0; cursor:pointer; border:0; width:100%; height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:14px; text-align:center; color:#fff; padding:16px; background:linear-gradient(135deg,#1f2937 0%,#0f172a 100%); }
  .cover:hover { background:linear-gradient(135deg,#273449 0%,#0f172a 100%); }
  .cover .teams { font-size:20px; font-weight:700; line-height:1.25; }
  .cover .play { display:inline-flex; align-items:center; justify-content:center; width:56px; height:56px; border-radius:50%; background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.35); }
  .cover .play svg { width:22px; height:22px; margin-left:3px; fill:#fff; }
  .cover .hint { font-size:12px; color:#b9c2cf; }
  iframe { position:absolute; inset:0; width:100%; height:100%; border:0; }
  .topmask { position:absolute; top:0; left:0; right:0; height:52px; background:#0b0d10; color:#fff; display:flex; align-items:center; justify-content:space-between; padding:0 12px; pointer-events:none; z-index:2; font-size:13px; font-weight:600; }
  .topmask .src { font-size:11px; font-weight:600; color:#ff9aa2; letter-spacing:.04em; }
  .closebtn { pointer-events:auto; cursor:pointer; background:rgba(255,255,255,.16); border:0; color:#fff; border-radius:8px; padding:5px 10px; font-size:12px; }
  .closebtn:hover { background:rgba(255,255,255,.3); }
  .meta { padding:12px 14px 14px; }
  .meta .teams { font-size:15px; font-weight:700; }
  .source-line { font-size:12px; color:#8a93a0; margin-top:4px; }
  .empty { text-align:center; color:#5b6470; background:#fff; border:1px dashed #d7dbe0; border-radius:14px; padding:40px 20px; margin-top:18px; }
  footer { margin-top:30px; font-size:12px; color:#8a93a0; text-align:center; }
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>⚽ WK 2026 — Samenvattingen</h1>
      <p class="sub">Bron: <strong>NOS Sport</strong> · bijgewerkt op __UPDATED__</p>
      <div class="spoiler-note"><span>🙈</span> Spoilervrij — geen uitslagen of standen. Klik op een kaart om af te spelen.</div>
    </header>
    <div id="days"></div>
    <footer>Gegroepeerd per wedstrijddag (Amerikaanse tijd). Wordt elke ochtend automatisch ververst. Sluit een video met ✕ om YouTube-eindschermen (kunnen uitslagen tonen) te vermijden.</footer>
  </div>
<script>
  const MATCHES = __DATA__;
  const ORIGIN = encodeURIComponent(window.location.origin);
  const days = document.getElementById("days");
  function playIcon(){ return '<span class="play"><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></span>'; }
  function makeCover(player, m){
    const c=document.createElement("button"); c.className="cover";
    c.innerHTML='<div class="teams">'+m.teams+'</div>'+playIcon()+'<div class="hint">Samenvatting · NOS</div>';
    c.addEventListener("click",function(){ playVideo(player,m); });
    return c;
  }
  function makeCard(m){
    const card=document.createElement("div"); card.className="card";
    const player=document.createElement("div"); player.className="player";
    player.appendChild(makeCover(player,m));
    const meta=document.createElement("div"); meta.className="meta";
    meta.innerHTML='<div class="teams">'+m.teams+'</div><div class="source-line">Samenvatting: NOS Sport</div>';
    card.appendChild(player); card.appendChild(meta);
    return card;
  }
  function render(){
    days.innerHTML="";
    if(!MATCHES.length){ days.innerHTML='<div class="empty">Nog geen samenvattingen beschikbaar. De pagina wordt elke ochtend bijgewerkt.</div>'; return; }
    let curKey=null, grid=null;
    MATCHES.forEach(function(m){
      if(m.day_key!==curKey){
        curKey=m.day_key;
        const group=document.createElement("div"); group.className="daygroup";
        const head=document.createElement("div"); head.className="dayhead";
        head.innerHTML='<span>'+(m.day_label||"")+'</span><span class="tz">wedstrijddag · VS-tijd</span>';
        grid=document.createElement("div"); grid.className="grid";
        group.appendChild(head); group.appendChild(grid); days.appendChild(group);
      }
      grid.appendChild(makeCard(m));
    });
  }
  function playVideo(player,m){
    player.innerHTML="";
    const iframe=document.createElement("iframe");
    iframe.src="https://www.youtube-nocookie.com/embed/"+m.id+"?autoplay=1&rel=0&modestbranding=1&playsinline=1&iv_load_policy=3&origin="+ORIGIN;
    iframe.allow="autoplay; encrypted-media; picture-in-picture; fullscreen";
    iframe.allowFullscreen=true;
    const mask=document.createElement("div"); mask.className="topmask";
    mask.innerHTML='<span>'+m.teams+' &nbsp;<span class="src">NOS</span></span>';
    const close=document.createElement("button"); close.className="closebtn"; close.textContent="✕ sluiten";
    close.addEventListener("click",function(e){ e.stopPropagation(); player.innerHTML=""; player.appendChild(makeCover(player,m)); });
    mask.appendChild(close);
    player.appendChild(iframe); player.appendChild(mask);
  }
  render();
</script>
</body>
</html>
"""


def render_html(matches):
    # matches is al gesorteerd op publicatietijd (nieuwste eerst).
    data = []
    for m in matches:
        key, label = us_matchday(m.get("published", ""))
        data.append({"id": m["id"], "teams": m["teams"],
                     "day_key": key, "day_label": label})
    # groepeer op dag, nieuwste dag eerst; binnen een dag blijft de
    # nieuwste-eerst-volgorde behouden (stabiele sort).
    data.sort(key=lambda x: x["day_key"], reverse=True)
    today = datetime.date.today()
    updated = f"{today.day} {MONTHS[today.month]} {today.year}"
    page = PAGE_TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    page = page.replace("__UPDATED__", updated)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(page)


def main():
    matches = load_matches()
    matches = update_matches(matches)
    save_matches(matches)
    render_html(matches)
    print(f"{len(matches)} samenvatting(en) op de pagina.")


if __name__ == "__main__":
    main()

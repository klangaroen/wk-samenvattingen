#!/usr/bin/env python3
"""
Genereert een spoilervrije pagina met NOS WK 2026-samenvattingen.

Draait in GitHub Actions (open netwerk):
- haalt de nieuwste video's van het YouTube-kanaal NOS Sport op (RSS),
- filtert op WK 2026-toernooisamenvattingen,
- STRIPT elke uitslag/score uit de titel (alleen neutrale landnamen blijven over),
- bewaart alles in matches.json (historie groeit aan),
- schrijft index.html, gegroepeerd per wedstrijddag (Amerikaanse tijd),
  mobielvriendelijk en met een WK-uitstraling.

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

# Vlaggen per land (Nederlandse namen zoals NOS ze schrijft).
FLAGS = {
    "nederland": "🇳🇱", "belgië": "🇧🇪", "belgie": "🇧🇪", "duitsland": "🇩🇪",
    "frankrijk": "🇫🇷", "spanje": "🇪🇸", "portugal": "🇵🇹", "engeland": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "italië": "🇮🇹", "italie": "🇮🇹", "brazilië": "🇧🇷", "brazilie": "🇧🇷",
    "argentinië": "🇦🇷", "argentinie": "🇦🇷", "mexico": "🇲🇽",
    "zuid-afrika": "🇿🇦", "zuid-korea": "🇰🇷", "tsjechië": "🇨🇿", "tsjechie": "🇨🇿",
    "japan": "🇯🇵", "verenigde staten": "🇺🇸", "vs": "🇺🇸", "canada": "🇨🇦",
    "kroatië": "🇭🇷", "kroatie": "🇭🇷", "marokko": "🇲🇦", "senegal": "🇸🇳",
    "ghana": "🇬🇭", "nigeria": "🇳🇬", "uruguay": "🇺🇾", "colombia": "🇨🇴",
    "ecuador": "🇪🇨", "zwitserland": "🇨🇭", "denemarken": "🇩🇰", "polen": "🇵🇱",
    "servië": "🇷🇸", "servie": "🇷🇸", "australië": "🇦🇺", "australie": "🇦🇺",
    "iran": "🇮🇷", "saoedi-arabië": "🇸🇦", "saoedi-arabie": "🇸🇦", "qatar": "🇶🇦",
    "egypte": "🇪🇬", "kameroen": "🇨🇲", "ivoorkust": "🇨🇮", "tunesië": "🇹🇳",
    "tunesie": "🇹🇳", "algerije": "🇩🇿", "costa rica": "🇨🇷", "peru": "🇵🇪",
    "chili": "🇨🇱", "paraguay": "🇵🇾", "wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "schotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "ierland": "🇮🇪", "noorwegen": "🇳🇴", "zweden": "🇸🇪", "oostenrijk": "🇦🇹",
    "turkije": "🇹🇷", "griekenland": "🇬🇷", "oekraïne": "🇺🇦", "oekraine": "🇺🇦",
    "hongarije": "🇭🇺", "slowakije": "🇸🇰", "slovenië": "🇸🇮", "slovenie": "🇸🇮",
    "roemenië": "🇷🇴", "roemenie": "🇷🇴", "ijsland": "🇮🇸", "nieuw-zeeland": "🇳🇿",
    "panama": "🇵🇦", "honduras": "🇭🇳", "jamaica": "🇯🇲", "venezuela": "🇻🇪",
    "bolivia": "🇧🇴", "litouwen": "🇱🇹", "kaapverdië": "🇨🇻", "kaapverdie": "🇨🇻",
    "curaçao": "🇨🇼", "curacao": "🇨🇼", "haïti": "🇭🇹", "haiti": "🇭🇹",
    "jordanië": "🇯🇴", "jordanie": "🇯🇴", "oezbekistan": "🇺🇿", "nieuw zeeland": "🇳🇿",
}


def flag_for(name):
    return FLAGS.get(name.lower().strip(), "⚽")


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
    t = re.sub(r"\d+\s*[-–:]\s*\d+", " ", title)
    t = re.sub(r"\d", " ", t)
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
            continue
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
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0b6e3b">
<title>WK 2026 — Samenvattingen (spoilervrij)</title>
<style>
  :root{
    color-scheme: light;
    --green:#0b7a40; --green-d:#075c30; --ink:#16261c; --muted:#5f6f66;
    --bg:#eef3ee; --card:#ffffff; --line:#dfe7e1; --accent:#f4c430;
  }
  *{box-sizing:border-box;}
  html,body{margin:0;}
  body{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    background:var(--bg); color:var(--ink);
    -webkit-font-smoothing:antialiased;
  }

  /* ---- Hero / veld ---- */
  .hero{
    position:relative; overflow:hidden; color:#fff;
    background:
      repeating-linear-gradient(90deg, rgba(255,255,255,.05) 0 38px, rgba(0,0,0,.04) 38px 76px),
      linear-gradient(135deg, var(--green) 0%, var(--green-d) 100%);
    padding: calc(env(safe-area-inset-top) + 26px) 18px 22px;
  }
  .hero::after{ /* middenlijn-cirkel sfeer */
    content:""; position:absolute; right:-60px; top:-60px; width:220px; height:220px;
    border:3px solid rgba(255,255,255,.14); border-radius:50%;
  }
  .hero-inner{max-width:1000px; margin:0 auto; position:relative;}
  .badge{
    display:inline-flex; align-items:center; gap:7px; font-size:12px; font-weight:700;
    letter-spacing:.06em; text-transform:uppercase;
    background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.25);
    padding:5px 11px; border-radius:999px;
  }
  .hero h1{ margin:12px 0 4px; font-size:clamp(24px,6vw,38px); line-height:1.05; font-weight:800; }
  .hero p{ margin:0; font-size:clamp(13px,3.6vw,15px); color:rgba(255,255,255,.9); }
  .pills{ display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }
  .pill{
    display:inline-flex; align-items:center; gap:6px; font-size:12px; font-weight:600;
    background:rgba(0,0,0,.18); border:1px solid rgba(255,255,255,.2);
    padding:6px 11px; border-radius:999px;
  }
  .pill.nos .dot{ width:8px; height:8px; border-radius:50%; background:var(--accent); }

  /* ---- Layout ---- */
  .wrap{ max-width:1000px; margin:0 auto; padding:6px clamp(12px,4vw,18px) 40px; }

  .dayhead{
    display:flex; align-items:center; gap:10px; margin:26px 2px 12px;
  }
  .dayhead .chip{
    background:var(--green); color:#fff; font-weight:700; font-size:14px;
    padding:7px 13px; border-radius:999px; white-space:nowrap;
  }
  .dayhead .ln{ flex:1; height:1px; background:var(--line); }
  .dayhead .tz{ font-size:12px; color:var(--muted); font-weight:600; white-space:nowrap; }

  .grid{
    display:grid; gap:clamp(12px,3.2vw,18px);
    grid-template-columns:repeat(auto-fill, minmax(min(100%,320px),1fr));
  }

  .card{
    background:var(--card); border:1px solid var(--line); border-radius:18px;
    overflow:hidden; box-shadow:0 2px 10px rgba(8,40,22,.06);
    transition:transform .15s ease, box-shadow .15s ease;
  }
  @media(hover:hover){ .card:hover{ transform:translateY(-3px); box-shadow:0 10px 24px rgba(8,40,22,.12);} }

  .player{ position:relative; width:100%; aspect-ratio:16/9; background:#0b0d10; }
  .cover{
    position:absolute; inset:0; cursor:pointer; border:0; width:100%; height:100%;
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    gap:10px; text-align:center; color:#fff; padding:14px;
    background:
      repeating-linear-gradient(90deg, rgba(255,255,255,.04) 0 26px, rgba(0,0,0,.05) 26px 52px),
      linear-gradient(135deg,#16382a 0%,#0d1f17 100%);
  }
  .cover .flags{ font-size:34px; line-height:1; display:flex; align-items:center; gap:12px; }
  .cover .flags .x{ font-size:16px; opacity:.7; font-weight:700; }
  .cover .teams{ font-size:18px; font-weight:800; line-height:1.2; }
  .cover .play{
    margin-top:2px; display:inline-flex; align-items:center; justify-content:center;
    width:54px; height:54px; border-radius:50%;
    background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.4);
  }
  .cover .play svg{ width:22px; height:22px; margin-left:3px; fill:#fff; }
  .cover .hint{ font-size:11px; letter-spacing:.05em; text-transform:uppercase; color:#cfe6d8; font-weight:700; }

  iframe{ position:absolute; inset:0; width:100%; height:100%; border:0; }
  .topmask{
    position:absolute; top:0; left:0; right:0; height:54px; background:#0b0d10; color:#fff;
    display:flex; align-items:center; justify-content:space-between; padding:0 12px;
    pointer-events:none; z-index:2; font-size:13px; font-weight:700;
  }
  .topmask .src{ font-size:11px; font-weight:700; color:var(--accent); letter-spacing:.04em; }
  .closebtn{
    pointer-events:auto; cursor:pointer; background:rgba(255,255,255,.18); border:0; color:#fff;
    border-radius:9px; padding:7px 11px; font-size:12px; font-weight:600;
  }
  .closebtn:active{ background:rgba(255,255,255,.34); }

  .meta{ padding:12px 14px 14px; display:flex; align-items:center; gap:10px; }
  .meta .mflags{ font-size:20px; line-height:1; }
  .meta .mteams{ font-size:15px; font-weight:800; }
  .meta .msrc{ font-size:11px; color:var(--muted); font-weight:600; margin-top:1px; }

  .empty{
    text-align:center; color:var(--muted); background:var(--card);
    border:1px dashed #c7d3cb; border-radius:16px; padding:42px 20px; margin-top:20px;
  }
  footer{ margin-top:30px; font-size:12px; color:var(--muted); text-align:center; line-height:1.6; }
</style>
</head>
<body>
  <div class="hero">
    <div class="hero-inner">
      <span class="badge">⚽ FIFA WK 2026</span>
      <h1>Samenvattingen</h1>
      <p>Spoilervrij — geen uitslagen, geen standen. Tik op een wedstrijd om te kijken.</p>
      <div class="pills">
        <span class="pill nos"><span class="dot"></span>Bron: NOS Sport</span>
        <span class="pill">🙈 Spoilervrij</span>
        <span class="pill">🔄 Bijgewerkt op __UPDATED__</span>
      </div>
    </div>
  </div>

  <div class="wrap">
    <div id="days"></div>
    <footer>
      Gegroepeerd per wedstrijddag (Amerikaanse tijd) · nieuwste bovenaan.<br>
      Sluit een video met ✕ om de eindschermen van YouTube (kunnen uitslagen tonen) te vermijden.
    </footer>
  </div>

<script>
  const MATCHES = __DATA__;
  const ORIGIN = encodeURIComponent(window.location.origin);
  const days = document.getElementById("days");

  function playIcon(){ return '<span class="play"><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></span>'; }
  function flagsHtml(m, big){
    const cls = big ? 'flags' : 'mflags';
    return '<div class="'+cls+'">'+(m.flag_home||'⚽')+(big?'<span class="x">vs</span>':' ')+(m.flag_away||'⚽')+'</div>';
  }

  function makeCover(player, m){
    const c=document.createElement("button"); c.className="cover";
    c.innerHTML=flagsHtml(m,true)+'<div class="teams">'+m.teams+'</div>'+playIcon()+'<div class="hint">Samenvatting · NOS</div>';
    c.addEventListener("click",function(){ playVideo(player,m); });
    return c;
  }
  function makeCard(m){
    const card=document.createElement("div"); card.className="card";
    const player=document.createElement("div"); player.className="player";
    player.appendChild(makeCover(player,m));
    const meta=document.createElement("div"); meta.className="meta";
    meta.innerHTML=flagsHtml(m,false)+'<div><div class="mteams">'+m.teams+'</div><div class="msrc">Samenvatting · NOS Sport</div></div>';
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
        head.innerHTML='<span class="chip">'+(m.day_label||"")+'</span><span class="ln"></span><span class="tz">VS-tijd</span>';
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
    mask.innerHTML='<span>'+(m.flag_home||'')+' '+m.teams+' '+(m.flag_away||'')+' &nbsp;<span class="src">NOS</span></span>';
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
        parts = re.split(r"\s+–\s+", m["teams"])
        home = parts[0] if parts else m["teams"]
        away = parts[1] if len(parts) > 1 else ""
        data.append({
            "id": m["id"], "teams": m["teams"],
            "day_key": key, "day_label": label,
            "flag_home": flag_for(home),
            "flag_away": flag_for(away) if away else "",
        })
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

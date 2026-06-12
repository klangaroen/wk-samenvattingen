# WK 2026 — spoilervrije samenvattingen (cloud)

Een pagina die elke ochtend automatisch de nieuwste NOS-samenvattingen toont,
**zonder uitslagen of standen**. Draait volledig in de cloud (GitHub), dus je
laptop hoeft niet aan te staan. Werkt ook op je mobiel.

## Eenmalige opzet (± 5 min)

1. **Maak een GitHub-account** (als je die nog niet hebt): https://github.com
2. **Maak een nieuwe repository**: knop *New* → naam bijv. `wk-samenvattingen`
   → **Public** → *Create repository*.
3. **Upload deze bestanden** naar de repo (knop *Add file → Upload files*,
   sleep alles erin, daarna *Commit changes*):
   - `generate.py`
   - `index.html`
   - `matches.json`
   - de map `.github/workflows/update.yml` (behoud de mappenstructuur!)
4. **Zet GitHub Pages aan**: repo → *Settings* → *Pages* →
   *Source: Deploy from a branch* → branch **main** / map **/(root)** → *Save*.
   Na een minuutje krijg je je url: `https://<jouw-gebruikersnaam>.github.io/wk-samenvattingen/`
5. **Eerste keer vullen**: repo → tab *Actions* → workflow *Update WK samenvattingen*
   → knop *Run workflow*. (Krijg je de melding dat workflows uit staan, klik
   eerst op *I understand my workflows, go ahead and enable them*.)

Klaar. Sla de Pages-url op je telefoon op (bijv. als snelkoppeling op je
beginscherm).

## Hoe het werkt

- `.github/workflows/update.yml` draait **elke ochtend om 06:00 NL-tijd**
  (cron `0 4 * * *` = 04:00 UTC in de zomer). Staat de tijd er in de winter een
  uur naast? Zet de cron dan op `0 5 * * *`.
- `generate.py` haalt de nieuwste video's van het YouTube-kanaal **NOS Sport**,
  filtert op WK 2026-samenvattingen, **verwijdert elke score uit de titel** en
  bouwt `index.html`. Alle gevonden wedstrijden worden bewaard in `matches.json`
  zodat de historie blijft staan.
- De pagina toont alleen **landnamen + "NOS"**. De video start pas na een klik
  en de YouTube-titelbalk (met de uitslag) wordt afgedekt.

## Belangrijk om te testen

Sommige omroepen blokkeren het embedden van hun YouTube-video's op andere
sites. Werkt een video niet (foutmelding 153) ook op de gepubliceerde Pages-url,
dan blokkeert NOS het embedden en moeten we een andere bron of weergave kiezen.
Lokaal openen van `index.html` (`file://`) geeft die fout sowieso — test dus
altijd via de `https://...github.io`-url.

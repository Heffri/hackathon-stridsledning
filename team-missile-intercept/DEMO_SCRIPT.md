# Smart Stridsledning — Demo Script (4 min)

> Browserbaserat arkadspel i luftförsvarsgenren. Tower Defense möter Kerbal Space Program — byggt kring Saabs Boreal Passage-scenario.

---

## [0:00–0:30] Intro & Pitch

**Säg:**
- "Vi har byggt ett realtids-luftförsvarsspel i webbläsaren."
- "Blue försvarar tre Saab-namngivna baser med 9 robotsystem. Red attackerar med drönare, kryssningsrobotar, ballistiska missiler och hypersoniska glidkroppar."
- "Båda sidor styrs av AI — spelaren kan justera försvarsuppställningen före match."

**Visa:** Kartan med Boreal Passage-terräng, tre baser (Main Base, Spear Point, Firewatch), utplacerade robotsystem med avståndscirklar.

---

## [0:30–1:30] Live Demo — Starta match

**Gör:**
1. Välj Layout B (eller nuvarande uppställning)
2. Dra en PAC-3 närmare Spear Point — "vi kan flytta system i realtid"
3. Klicka **Start Match**, sätt hastighet till 5–10x

**Kommentera medan det spelas:**

### Våg 1–2 (drönare + kryssning)
- "Här kommer drönarna — CIWS och RBS-70 tar hand om dem på kort räckvidd"
- "Kryssningsrobotarna flyger S-kurvor, IRIS-T SLS fångar dem på 40 km"
- Peka på **engagementslinjer** (gröna linjer från interceptor till mål)

### Våg 3–4 (ballistiska)
- "Nu kommer ballistiska missiler — Mach 13, 40 km höjd"
- "PAC-3 och PAC-2 skjuter i lager: tre interceptorer per hot"
- Peka på AI-dashboarden: "AI:n bestämmer automatiskt vilken robot som passar"

### Våg 5 (HGV-mättnad)
- "Hypersonisk glidkropp — Mach 17. Svåraste hotet."
- "Alla system skjuter nu. Tight fönster."

---

## [1:30–2:15] Klick-inspektion & AI-transparens

**Gör:** Pausa (Space). Klicka på en interceptor i luften.

**Visa statuspanelen:**
- Typ, Mach-tal, G-last, bränsle kvar, mål, avstånd, kostnad
- "Varje interceptor har bränsle — flamman slocknar vid burnout, sen glidfas"

**Visa dashboards:**
- Blå dashboard: interceptionsgrad, aktiva robotar per typ, redo-launchers
- Röd dashboard: aktiva hot per typ, skadade baser med HP%
- "AI:n skippar hot mot förstörda baser — sparar budget till levande mål"

---

## [2:15–3:00] Tekniska höjdpunkter

Säg 3–4 av dessa:

1. **Proportionalnavigering (PN)** — riktig styrlag, inte leksaksballistik. Varje interceptor beräknar avskärningskurs 20 ggr/s.

2. **Bränslefysik** — varje robottyp har bränsletid (PAC-3: 35s, SLS: 30s). Efter burnout: glidfas med halv manöverförmåga. Stallgräns 200 m/s.

3. **HGV-energiblödning** — hypersoniska glidkroppar tappar fart quadratiskt med sväng-G. Undviker → tappar energi. Rakt → lättare att träffa.

4. **Kostnadsekonomi** — Blue: $120M budget. PAC-3 kostar $3M per skott. Tre skott mot en HGV = $9M. HGV gör 40 HP skada. Varje beslut har en prislapp.

5. **Sitemedveten AI** — Blue slutar försvara förstörda baser. Red fokuserar eld på svagaste överlevande basen.

6. **Mättningseld** — AI:n skjuter upp till 3 interceptorer per hot, i lager (PAC-3 → PAC-2 → SLM), tills förväntad skada ≥ hotets HP.

---

## [3:00–3:30] Siffror att nämna

| Siffra | Värde |
|--------|-------|
| Hotens hastigheter | Drönare 100 m/s, Kryssning 250 m/s, Ballistisk Mach 13, HGV Mach 17 |
| Interceptorräckvidd | CIWS 4 km → PAC-2 70 km (6 lager) |
| Blue budget | $120M — varje skott kostar |
| Baser | 3 st, 100 HP var — Red vinner om en dör |
| Vinstsats | ~70% Blue-vinst med rätt uppställning |
| Arenan | 350 × 150 km — verklig Boreal Passage-skala |
| Fysik-tick | 20 Hz (0.05s), rendering 60 fps, WS 15 Hz |

---

## [3:30–4:00] Avslutning

**Säg:**
- "Taktisk sandlåda där båda sidor spelar under ekonomiska begränsningar och riktig fysik."
- "AI:n är transparent — man ser varje beslut, varje kostnad, varje avvägning."
- "Byggt i Python + Three.js, körs i Chrome, ingen installation."

**Om tid:** Visa slutskärmen med matchstatistik (interceptionsgrad, kostnadskvot, site-HP).

---

## Förberedelse-checklista

- [ ] Starta servern: `cd backend && python server.py`
- [ ] Öppna `http://localhost:5174` i Chrome (fullskärm F11)
- [ ] Välj Layout B, verifiera att kartan ser bra ut
- [ ] Ha OBS redo med inspelad backup
- [ ] Sätt hastighet till 1x vid start, öka till 5–10x efter Våg 1
- [ ] Testa Space (paus), R (kameraåterställning), +/- (hastighet)
- [ ] Kör ett testmatch före presentationen

---

## Nödplan

Om live-demon kraschar:
1. Växla till inspelad backup i OBS
2. Fortsätt kommentera som vanligt
3. "Vi kör inspelat — samma match, samma AI"

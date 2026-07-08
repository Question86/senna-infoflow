# senna-infoflow

`senna-infoflow` ist ein öffentlicher Signalfilter für User Yps / AXI0M.

Das System ist kein vollständiger Nachrichtendienst und behauptet nicht, die Welt vollständig zu überwachen. Es liest nur konfigurierte, öffentliche, freigegebene Quellen. Keine privaten Accounts. Keine Logins. Keine Paywall-/Datenbank-Umgehung. Kein Scraping gegen klare Verbote.

## Grundsatz

Nicht jeder Feed ist gleich wertvoll.

Ein offizieller großer Emittent wie FED, EZB, BIS, CISA oder NOAA bekommt Glaubwürdigkeit, aber keine automatische Ranking-Dominanz. Ein kleiner frühes Signal, etwa ein lokaler Waldbrand, ein Blackout, ein Streik, ein Port-/Pipeline-Ausfall, ein Repo-Security-Hinweis oder eine Lieferkettenstörung, bleibt sichtbar, wenn es konkret, neu oder dynamisch ist.

```text
Glaubwrdigkeit ja.
Megaphon-Dominanz nein.
Kleine Anfangsdynamiken bleiben sichtbar.
Vendor-/Eigenfeeds zählen nicht wie Weltlage.
```

## Architektur in einem Satz

```text
konfigurierte öffentliche Quellen
↓ Lane-Merge
↓ Fetch mit Budget/Timeout
↓ Dedup & Tagespool
↓ Debias
↓ Netzwerk-/Resonanzranking
↓ Health/Manifest/Briefings
↓ Handoff für Senna
```

Die ausführliche Architektur liegt in [`docs/architecture.md` (docs/architecture.md).

## Quellen und Lanes

Die Quellen entstehen im Workflow aus mehreren Konfigurationsdateien:

```text
config/sources.yaml          # Basisquellen
config/hot_sources.yaml      #  schnelle 5-Minuten-Lane
config/macro_sources.yaml    # Wirtschaft / Politik / Makro, 15-Minuten-Lane oder manuell
```

Im laufenden GitHub-Action-Run werden Hot- und Macro-Overlays temporär in `config/sources.yaml` gemerged. Nach jedem Lauf schreibt das System zusätzlich:

```text
briefings/source_manifest.json
briefings/source_manifest.md
```

Dort steht, welche Quellen in diesem Run tatsächlich aktiv waren, inklusive Lane, Typ, Klasse und Host.

## Lanes

### Hot-Lane

Läuft alle 5 Minuten.

Typische Quellen:

- GitHub-/Dev-Signale
- HN / öffentliche schnelle Tech-Signale
- GDACS / USGS / GEOFON / NOAA
- manuelle öffentliche Hinweise
- ausgewählte öffentliche Risiko-/Odds-Proxies, sofern abrufbar

Diese Lane ist schnell, aber anfällig für Spezialfeed-Bias. Deshalb wird sie durch Debias, Resonanzranking und Source-Governance begrenzt.

### Macro-/Policy-Lane

Läuft alle 15 Minuten oder bei manuellem Dispatch.

Typische Quellen:

- Federal Reserve
- European Central Bank
- Bank for International Settlements
- OECD
- GDELT-Makro-/Politik-Sensoren

Diese Lane ergänzt Wirtschaft, Politik, Zinsen, Zentralbanken, Sanktionen, Märkte, Wahlen, Unruhe und globale Policy-Signale. Sie darf wichtig sein, aber nicht allein das Lagebild dominieren.

## Unterstützte Quellentypen

| Typ | Zweck |
| --- | --- |
| `rss` | RSS/Atom-Feeds lesen |
| `github_search` | GitHub Search API nutzen, optional mit `GITHUB_TOKEN` |
| `reddit_json` | Öffentliche Reddit-JSON-Endpunkte; aktuell oft 403/instabil |
| `hackernews` | Öffentliche Hacker-News-Suche über Algolia |
| `webpage_check` | Einzelne Webseiten höflich und begrenzt prüfen |
| `manual_note` | Von User Yps freigegebene Hinweise aus Inbox-Dateien |

## Vorsortierung und Ranking

Relevanz entsteht aus mehreren Schichten:

```text
keyword score
+ recency
+ watchgraph modules
+ source credibility
+ source breadth
+ momentum
+ baseline deviation
+ early-signal bonus
- duplicate/noise pressure
- dominance penalty
- source-bias caps
```

Wichtige Dateien:

```text
scripts/debias_findings_postprocess.py
scripts/network_hub_postprocess.py
scripts/resonance_rank_postprocess.py
scripts/source_quality_guard.py
config/resonance_ranking.yaml
config/source_governance.yaml
```

### Bias-Regeln
Vendor-/Eigenfeeds, einzelne GitHub-Repos, Odds-/Prediction-Proxies und Social-/Platform-Signale bleiben sichtbar, werden aber ohne unabhängige Bestätigung oder klare Hochsignal-Begriffe begrenzt.

Beispiele für Hochsignal:

- actively exploited
- exploited in the wild
- CISA KEV
- zero-day
- emergency patch
- evacuation order
- port closure
- pipeline outage
- central bank emergency

Die Regel ist absichtlich streng:


```text
Ein Feed darf früh warnen.
Er darf ohne Resonanz nicht die Welt erklären.
```

## Source-Governance

`config/source_governance.yaml` definiert, welche Degeneration das Repo vermeiden soll:

- zu viele generische Mainstream-/Major-Media-Quellen;
- zu starke Single-Host-oder Single-Class-Dominanz;
- zu viele Vendor-/Repo-/Odds-Signale ohne Gegenquelle;
- unklare oder fehlende Source-Klassen;
- fehlende Early-Signal-Abdeckung.

`scripts/source_quality_guard.py` wertet nach jedem Run Manifest, Netzerk und Briefing aus und schreibt:


```text
briefings/source_quality.json
briefings/source_quality.md
```

Der Guard ist eine Frühwarnschicht. Er bricht den Workflow nicht bei jedem Warnsignal, aber macht Degeneration sichtbar.

## Wichtige Outputs


```text
briefings/latest.json           # aktueller Dashboard-/Tagespool
briefings/latest.md             # menschenlesbare Kurzlage
briefings/network.json          # Cluster / Network Hub / Resonanzranking
briefings/breaking.md          # Hot-/Breaking-Signale
briefings/source_manifest.json  # aktive Quellen nach Overlay-Merge
briefings/source_manifest.md    # lesbare Quellenübersicht
briefings/source_quality.json   # Source-Governance-Auswertung
briefings/source_quality.md     #  lesbare Source-Governance-Auswertung
reports/latest_atom.md          # kanonischer Run-Atom
data/YYYY-MM-DD/findings.json   # Tagesfundus
state/seen.json                 # Dedup-State
state/velocity.json             # Momentum-State
```

## GitHub Actions

Workflow:


```text
.github/workflows/monitor.yml
```

Takt:


```text
*/5 * * * *

```

Governance:

```text
Job timeout: 8 Minuten
Monitor timeout: 5 Minuten
Hot-Lane: alle 5 Minuten
Macro-Lane: alle 15 Minuten oder manuell
MAX_ITEMS_PER_SOURCE: 6 im Scheduled-Run
HTTP timeout: 8 Sekunden
HTTP retry attempts: 1 im Scheduled-Run
```

Der Scheduled-Run ist absichtlich knapp budgetiert. Breite entsteht nicht durch massenhaft Items pro Feed, sondern durch bessere Quellmischung, Resonanz, Momentum und Baseline-Abweichung.

## Grenzen

Das System prüft keine privaten Accounts, keine geschlossenen Communities, keine Logins, keine bezahlten Datenbanken und keine nicht autorisierten Schnittstellen.

Nicht erlaubt:

- Doxxing
- Stalking
- Credential-Diebstahl
- Zugriffsumgehung
- Massenscraping
- private personenbezogene Daten Dritter
- unbestätigte Anschuldigungen als Fakten
- Wett-/Finanzberatung aus Odds- oder Marktdaten

## Wie Senna das Repo lesen soll

Für aktuelle Lage zuerst lesen:


```text
briefings/latest.json
briefings/network.json
briefings/source_quality.json
briefings/source_manifest.json
reports/latest_atom.md
```

Nicht aus `README.md` ableiten, welche Quellen im letzten Run aktiv waren. Dafür ist `briefings/source_manifest.json` da.

## Ausbaurichtung

Vorwärts geht dieses Repo nicht durch mehr generische Feeds, sondern durch bessere Sensorik:

1. mehr kleine, konkrete Frühindikatoren mit klarer Klasse;
2. bessere Cross-Source-Bestätigung;
3. stärkere Baseline-/Momentum-Modelle;
4. transparente Source-Qualität pro Run;
5. weniger Single-Host-, Vendor- und Mainstream-Dominanz;
6. bessere Handoffs für kurze, handlungsfähige Briefings.

END OF DOCUMENT

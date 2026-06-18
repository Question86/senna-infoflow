# senna-infoflow

`senna-infoflow` ist ein öffentlicher Signalfilter für User Yps / AXI0M.

Das System ist kein vollständiger Nachrichtendienst und behauptet nicht, die Welt vollständig zu überwachen. Es liest nur konfigurierte, öffentliche, freigegebene Quellen. Keine privaten Accounts. Keine Logins. Keine Paywall-/Datenbank-Umgehung. Kein Scraping gegen klare Verbote.

## Aktueller Grundsatz

Nicht jeder Feed ist gleich wertvoll.

Ein offizieller großer Emittent wie FED, EZB oder BIS bekommt Glaubwürdigkeit, aber keine automatische Ranking-Dominanz. Ein kleiner frühes Signal, etwa ein lokaler Waldbrand, ein Blackout, ein Streik oder eine Lieferkettenstörung, bleibt sichtbar, wenn es konkret, neu oder dynamisch ist.

Kurz:

```text
Glaubwürdigkeit ja.
Megaphon-Dominanz nein.
Kleine Anfangsdynamiken bleiben sichtbar.
Vendor-/Eigenfeeds zählen nicht wie Weltlage.
```

## Was überwacht wird

Die Quellen entstehen im Workflow aus mehreren Konfigurationsdateien:

```text
config/sources.yaml        # Basisquellen
config/hot_sources.yaml    # schnelle 5-Minuten-Lane
config/macro_sources.yaml  # Wirtschaft / Politik / Makro, 15-Minuten-Lane oder manuell
```

Die alte Aussage „nur config/sources.yaml“ war falsch beziehungsweise veraltet. Im laufenden GitHub-Action-Run werden Hot- und Macro-Overlays temporär in `config/sources.yaml` gemerged.

Nach jedem Lauf schreibt das System zusätzlich:

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

Diese Lane ist schnell, aber anfällig für Spezialfeed-Bias.

### Macro-/Policy-Lane

Läuft alle 15 Minuten oder bei manuellem Dispatch.

Typische Quellen:

- Federal Reserve
- European Central Bank
- Bank for International Settlements
- OECD
- GDELT-Makro-/Politik-Sensoren

Diese Lane soll Wirtschaft, Politik, Zinsen, Zentralbanken, Sanktionen, Märkte, Wahlen, Unruhe und globale Policy-Signale ergänzen.

## Unterstützte Quellentypen

| Typ | Zweck |
| --- | --- |
| `rss` | RSS/Atom-Feeds lesen |
| `github_search` | GitHub Search API nutzen, optional mit `GITHUB_TOKEN` |
| `reddit_json` | Öffentliche Reddit-JSON-Endpunkte; aktuell oft 403/instabil |
| `hackernews` | Öffentliche Hacker-News-Suche über Algolia |
| `webpage_check` | Einzelne Webseiten höflich und begrenzt prüfen |
| `manual_note` | Von User Yps freigegebene Hinweise aus Inbox-Dateien |

## Bias-Regeln

Das System behandelt Quellen nicht mehr flach.

### Vendor-/Eigenfeeds

Snyk, PortSwigger und ähnliche Vendor-Feeds sind nützlich, aber nicht neutral. Sie senden stark über ihre eigene Domäne.

Deshalb gilt:

```text
Vendor-/Self-Feeds bleiben sichtbar,
werden aber ohne unabhängiges Hochsignal gecappt.
```

Beispiele für Hochsignal:

- actively exploited
- exploited in the wild
- CISA KEV
- zero-day
- emergency patch

### GitHub-Repo-Signale

Ein einzelnes GitHub-Repository ist ein Frühindikator, aber kein Weltlage-Beweis.

```text
Single-platform GitHub repo signals bleiben sichtbar,
dominieren aber ohne Resonanz nicht das Ranking.
```

### Odds-/Prediction-Proxies

Öffentliche Odds-Seiten sind Stimmungs-/Erwartungsproxies, keine Wahrheit und keine Handlungsempfehlung.

```text
Odds-Proxies werden ohne externe Bestätigung gecappt.
Keine Wettberatung.
```

### Falsch-positive Keywords

Das System hat eine Debias-Schicht:

```text
scripts/debias_findings_postprocess.py
```

Sie korrigiert unter anderem:

- `repo` darf nicht `report.aspx` als GitHub matchen
- `Who will win` darf nicht automatisch als WHO/Public-Health-Signal zählen
- Vendor-/GitHub-/Odds-Signale werden als solche gekennzeichnet und begrenzt

## Ranking-Schichten

Relevanz entsteht aus mehreren Komponenten:

```text
keyword score
+ recency
+ watchgraph modules
+ source credibility
+ source breadth
+ momentum
+ baseline deviation
+ early-signal bonus
- dominance penalty
- source-bias caps
```

Die Resonanzlogik liegt in:

```text
scripts/resonance_rank_postprocess.py
config/resonance_ranking.yaml
```

## Wichtige Outputs

```text
briefings/latest.json          # aktueller Delta-Run
briefings/latest.md            # menschenlesbare Kurzlage
briefings/network.json         # Cluster / Network Hub / Resonanzranking
briefings/breaking.md          # Hot-/Breaking-Signale
briefings/source_manifest.json # aktive Quellen nach Overlay-Merge
briefings/source_manifest.md   # lesbare Quellenübersicht
reports/latest_atom.md         # kanonischer Run-Atom
data/YYYY-MM-DD/findings.json  # Tagesfundus
state/seen.json                # Dedup-State
state/velocity.json            # Momentum-State
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
MAX_ITEMS_PER_SOURCE: 12
```

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
briefings/source_manifest.json
reports/latest_atom.md
```

Nicht aus `README.md` ableiten, welche Quellen im letzten Run aktiv waren. Dafür ist `briefings/source_manifest.json` da.

END OF DOCUMENT

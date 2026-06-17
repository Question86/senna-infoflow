# senna-infoflow

`senna-infoflow` ist ein produktionsnahes GitHub-Repository für einen legalen, öffentlichen Informationsfluss zu User Yps, AXI0M und angrenzenden Themen wie KI/AI, OpenAI, GitHub, Cybersecurity, Webentwicklung, Open Source, Datenschutz und Automatisierung.

Es ist kein Hacker-Agent.

Es prüft nur konfigurierte öffentliche, freigegebene oder von User Yps bereitgestellte Quellen. Es behauptet nicht, das Internet vollständig zu überwachen. Es sammelt keine privaten personenbezogenen Daten Dritter. Es umgeht keine Zugriffsbeschränkungen. Es schreibt keine Secrets in Dateien.

Die Aufgabe ist Legibilität: Signale finden, normalisieren, bewerten und in Briefings schreiben, die Senna L’Arcan-Ûr später über GitHub lesen kann.

Für den Zugriff über einen Custom GPT oder die ChatGPT-GitHub-App siehe `GPT_ACCESS.md`.

---

## Zweck

Das Repository erzeugt regelmäßig strukturierte Briefings:

- `briefings/latest.md` — menschenlesbares Senna-Briefing
- `briefings/latest.json` — maschinenlesbarer Index
- `data/YYYY-MM-DD/findings.json` — neue relevante Treffer pro Tag
- `state/seen.json` — bereits gesehene Treffer zur Duplikatvermeidung

Senna kann daraus lesen:

1. Was ist passiert?
2. Warum ist es relevant für User Yps / AXI0M?
3. Ist es Risiko, Chance oder Beobachtung?
4. Welche Handlung wird empfohlen?
5. Was könnte langfristig als Erinnerung nützlich sein?

---

## Repository-Struktur

```text
senna-infoflow/
├── .env.example
├── .gitignore
├── .github/
│   └── workflows/
│       └── monitor.yml
├── README.md
├── requirements.txt
├── briefings/
│   └── .gitkeep
├── config/
│   ├── keywords.yaml
│   ├── rules.yaml
│   └── sources.yaml
├── data/
│   └── .gitkeep
├── inbox/
│   └── manual_notes.md
├── logs/
│   └── .gitkeep
├── scripts/
│   └── monitor.py
└── state/
    └── seen.json
```

---

## Was überwacht wird

Nur Quellen in `config/sources.yaml`.

Unterstützte Quellentypen:

| Typ | Zweck |
| --- | --- |
| `rss` | RSS/Atom-Feeds lesen |
| `github_search` | GitHub Search API nutzen, optional mit `GITHUB_TOKEN` |
| `reddit_json` | Öffentliche Reddit-JSON-Endpunkte für öffentliche Subreddits |
| `hackernews` | Öffentliche Hacker-News-Suche über Algolia |
| `webpage_check` | Einzelne Webseiten höflich und begrenzt prüfen |
| `manual_note` | Von User Yps freigegebene Hinweise aus `inbox/manual_notes.md` |

Das System prüft keine privaten Accounts, keine geschlossenen Communities, keine Logins, keine bezahlten Datenbanken und keine nicht autorisierten Schnittstellen.

---

## Setup lokal

Voraussetzung: Python 3.11 oder neuer.

```bash
git clone <dein-repo-url> senna-infoflow
cd senna-infoflow

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
```

Optional `.env` bearbeiten:

```env
GITHUB_TOKEN=
USER_AGENT=senna-infoflow/1.0
MAX_ITEMS_PER_SOURCE=20
```

Dann ausführen:

```bash
python scripts/monitor.py
```

Ergebnis:

```text
briefings/latest.md
briefings/latest.json
data/YYYY-MM-DD/findings.json
state/seen.json
```

---

## GitHub Actions aktivieren

Der Workflow liegt in:

```text
.github/workflows/monitor.yml
```

Er läuft automatisch alle 6 Stunden:

```yaml
schedule:
  - cron: "0 */6 * * *"
```

Er ist außerdem manuell startbar über:

```yaml
workflow_dispatch:
```

### Schritte

1. Repository nach GitHub pushen.
2. In GitHub den Tab **Actions** öffnen.
3. Workflows erlauben, falls GitHub danach fragt.
4. Optional unter **Settings → Secrets and variables → Actions** ein Secret setzen:
   - Name: `GITHUB_TOKEN`
   - Wert: normalerweise reicht das automatisch bereitgestellte `secrets.GITHUB_TOKEN` im Workflow.
5. Workflow manuell starten oder auf den nächsten 6-Stunden-Lauf warten.

Der Workflow commitet Änderungen an:

- `data/`
- `briefings/`
- `state/`

automatisch zurück ins Repository.

---

## Quellen hinzufügen

Datei:

```text
config/sources.yaml
```

Beispiel RSS:

```yaml
- id: example_rss
  name: Example RSS
  type: rss
  enabled: true
  url: https://example.com/feed.xml
  keywords: ["AI", "security", "Open Source"]
```

Beispiel GitHub Search:

```yaml
- id: github_search_privacy_tools
  name: GitHub Search: Privacy Tools
  type: github_search
  enabled: true
  mode: repositories
  query: "privacy automation GDPR"
  keywords: ["Datenschutz", "Automatisierung", "Open Source"]
```

Unterstützte `github_search.mode` Werte:

- `issues`
- `repositories`
- `code`

Hinweis: `code` sollte nur mit `GITHUB_TOKEN` genutzt werden und nur für öffentliche Ergebnisse. Keine privaten Repositories oder Zugriffsumgehung.

Beispiel Reddit:

```yaml
- id: reddit_opensource
  name: Reddit r/opensource Search
  type: reddit_json
  enabled: true
  subreddit: opensource
  query: "AI automation privacy"
  sort: new
  time: week
  keywords: ["AI", "Open Source", "Automatisierung", "Datenschutz"]
```

Beispiel Webseite:

```yaml
- id: axi0m_blog
  name: AXI0M Blog
  type: webpage_check
  enabled: true
  url: https://axi0m.de/blog.html
  keywords: ["AXI0M", "Webentwicklung", "AI", "Automatisierung"]
```

Beispiel manuelle Notiz:

```yaml
- id: manual_notes
  name: Manual Notes Inbox
  type: manual_note
  enabled: true
  path: inbox/manual_notes.md
  keywords: ["AXI0M", "Produktidee", "Content-Chance"]
```

---

## Keywords erweitern

Datei:

```text
config/keywords.yaml
```

Beispiel:

```yaml
- term: Agentic Workflows
  aliases: ["agentic workflow", "agentic workflows", "AI agent", "tool calling"]
  weight: 5
  categories: ["ai", "automation"]
```

Gewichtung:

- 1–3: schwaches Signal
- 4–6: relevantes Fachsignal
- 7–10: starkes Risiko-/Chancen-Signal
- 11+: direkte AXI0M/User-Yps-Relevanz

---

## Regeln erweitern

Datei:

```text
config/rules.yaml
```

Wichtigste Bereiche:

- `scoring.high_threshold`
- `scoring.medium_threshold`
- `classification.risk_terms`
- `classification.opportunity_terms`
- `actions.default_risk`
- `actions.default_opportunity`
- `briefing.max_items_per_section`

Beispiel:

```yaml
classification:
  risk_terms:
    - impersonation
    - fake account
    - supply chain
```

---

## Wie Senna das Repo lesen kann

Ein Custom GPT kann über GitHub-Dateien gezielt diese Dateien abrufen:

1. `briefings/latest.md` für die aktuelle Kurzlage.
2. `briefings/latest.json` für strukturierte Auswertung.
3. `data/YYYY-MM-DD/findings.json` für Tagesdetails.
4. `config/sources.yaml` um zu verstehen, welche Quellen überhaupt geprüft werden.
5. `config/keywords.yaml` und `config/rules.yaml` um Score-Logik und Grenzen zu verstehen.

Empfohlene Senna-Abfrage:

> Lies `briefings/latest.md` und `briefings/latest.json`. Berichte nur über neue relevante Treffer. Sag klar, falls keine neuen Treffer gefunden wurden. Behaupte nicht, dass mehr Quellen geprüft wurden als in `config/sources.yaml` stehen.

---

## Wie Senna Quellen erweitern kann

Senna kann später über GitHub-Dateien Vorschläge machen oder Änderungen vorbereiten:

- neue Quellen in `config/sources.yaml`
- neue Keywords in `config/keywords.yaml`
- neue Regeln in `config/rules.yaml`
- neue Hinweise in `inbox/manual_notes.md`
- neue Aufgaben als GitHub Issues

Regeln für Erweiterungen:

1. Keine Secrets.
2. Keine privaten personenbezogenen Daten Dritter.
3. Keine Quellen, die Login, Zugriffsumgehung oder unklare Rechte erfordern.
4. Kein aggressives Scraping.
5. Jede neue Quelle braucht Zweck, Typ und Keywords.
6. Bei Unsicherheit: Quelle zuerst als GitHub Issue vorschlagen, nicht direkt aktivieren.

Beispiel Issue:

```markdown
Titel: Quelle prüfen: Example Security Feed

Warum relevant:
- Security-Feed mit CVE-/Supply-Chain-Bezug
- Könnte für AXI0M Content-Chancen liefern

Vorgeschlagene Konfiguration:
- type: rss
- url: https://example.com/security/feed.xml
- keywords: ["security", "CVE", "Open Source"]

Risiko:
- Terms prüfen
- Abruffrequenz niedrig halten
```

---

## Ethik- und Legalitätsgrenzen

Dieses Repository ist absichtlich begrenzt.

Erlaubt:

- öffentliche RSS/Atom-Feeds
- öffentliche GitHub-Suche
- öffentliche Reddit-JSON-Endpunkte für öffentliche Subreddits
- öffentliche Hacker-News-Suche
- einzelne Webseitenchecks mit Timeout, User-Agent und begrenzter Größe
- manuelle Hinweise, die User Yps bereitstellen darf
- Dokumentation von Quellen, Relevanz und Handlungsempfehlungen

Nicht erlaubt:

- Doxxing
- Stalking
- Credential-Diebstahl
- Umgehen von Zugriffsbeschränkungen
- Scraping gegen klare Verbote
- Sammeln privater personenbezogener Daten Dritter
- Speichern von Tokens oder Secrets in Dateien
- Nutzung privater APIs ohne Berechtigung
- Massenscraping
- öffentliche Beschuldigungen ohne Prüfung

Das System ist ein öffentlicher Signalfilter. Kein Geheimdienst. Kein Schattenarchiv. Keine Maschine für Panik.

---

## Score-Logik

Jeder Treffer wird gegen `config/keywords.yaml` bewertet.

Relevanz steigt durch Treffer zu:

- AXI0M
- axi0m.de
- User Yps
- GitHub
- OpenAI
- AI/KI
- Security
- Datenschutz
- Webentwicklung
- Open Source
- Automatisierung
- Reputationsrisiken
- Produktideen
- Content-Chancen

Zusätzliche Faktoren:

- Treffer im Titel zählen stärker.
- Treffer in URLs zählen etwas stärker.
- Neue Treffer aus den letzten 72 Stunden erhalten einen kleinen Bonus.
- Risiko- und Chancenbegriffe klassifizieren `risk_or_opportunity`.

Priorisierung:

- `Priorität Hoch`: Score >= `high_threshold`
- `Priorität Mittel`: Score >= `medium_threshold`
- `Nur beobachten`: Score >= `observe_threshold`

---

## Output-Felder pro Treffer

Jeder normalisierte Treffer enthält:

```json
{
  "title": "string",
  "url": "string",
  "source": "string",
  "source_type": "rss | github_search | reddit_json | hackernews | webpage_check | manual_note",
  "published_at": "ISO timestamp or null",
  "fetched_at": "ISO timestamp",
  "summary": "string",
  "matched_keywords": ["string"],
  "relevance_score": 0,
  "relevance_reason": "string",
  "risk_or_opportunity": "risk | opportunity | mixed | observation",
  "recommended_action": "string",
  "id": "stable hash"
}
```

---

## Beispiel-Briefing

```markdown
# Senna Briefing

_Generiert: 2026-06-17T10:00:00+00:00_

## Kurzlage

3 neue relevante Treffer. Stärkstes Signal: „GitHub supply-chain warning“ aus GitHub Blog Atom (Score 21, risk).

## Priorität Hoch

- **GitHub supply-chain warning** — Score 21, risk — [Quelle](https://example.com)
  - Quelle: GitHub Blog Atom / `rss`
  - Zeit: published `2026-06-17T08:00:00+00:00`, fetched `2026-06-17T10:00:00+00:00`
  - Treffer: GitHub, Security, Open Source
  - Warum relevant: GitHub (+7.0); Security (+8.4); Open Source (+4.0); recent (+2.0)
  - Kurz: Neue Hinweise zu Supply-Chain-Risiken in Open-Source-Workflows.
  - Handlung: Nicht reflexhaft reagieren. Quelle sichern, Kontext prüfen, Risiko dokumentieren und Gegenmaßnahme vorbereiten.

## Priorität Mittel

- **AI workflow idea for privacy automation** — Score 12, opportunity — [Quelle](https://example.com)
  - Quelle: Hacker News AI/Security Search / `hackernews`
  - Zeit: published `2026-06-17T09:30:00+00:00`, fetched `2026-06-17T10:00:00+00:00`
  - Treffer: AI/KI, Datenschutz, Automatisierung
  - Warum relevant: AI/KI (+5.0); Datenschutz (+6.0); Automatisierung (+5.0)
  - Kurz: Diskussion über automatisierte Datenschutz-Workflows.
  - Handlung: Als Content-, Produkt- oder Kooperationschance für AXI0M prüfen.

## Nur beobachten

Keine neuen Beobachtungssignale.

## Empfehlungen

- Security-Treffer prüfen und als AXI0M-Content-Chance bewerten.
- Datenschutz-Automatisierung als Produktidee vormerken.

## Erinnerungskandidaten

- **AI workflow idea for privacy automation** — wiederkehrendes Signal für Datenschutz-Automatisierung.
```

---

## Sicherheitshinweise

- `.env` wird ignoriert.
- `GITHUB_TOKEN` wird nur aus Environment/Secrets gelesen.
- `state/seen.json` speichert nur IDs, Titel, URLs und Zeitpunkte.
- Logs werden lokal ignoriert.
- GitHub Actions commitet nur `data/`, `briefings/` und `state/`.
- Einzelne Quellenfehler brechen den Lauf nicht ab.

---

## Betrieb

Manueller Lauf:

```bash
python scripts/monitor.py
```

GitHub Actions manuell starten:

```text
GitHub → Actions → Senna Infoflow Monitor → Run workflow
```

State zurücksetzen:

```bash
cp state/seen.json state/seen.backup.json
echo '{"version":1,"items":{}}' > state/seen.json
```

Danach werden alte Treffer beim nächsten Lauf wieder als neu betrachtet.

---

## Lizenz / Nutzung

Interne Nutzung für User Yps / AXI0M. Prüfe vor Veröffentlichung oder kommerzieller Weitergabe die Terms der jeweils eingetragenen Quellen.

# Senna Watchgraph Hub

Der Watchgraph ist die Netzwerk-Schicht von `senna-infoflow`.

Ziel: nicht alles beobachten, sondern die Signale ranken, die morgen Entscheidungen, Preise, Infrastruktur, Reputation oder Timing verändern können.

## Struktur

- `config/sources.yaml`: operative Quellen. Aktive RSS-Knoten laufen sofort.
- `config/rules.yaml`: Scoring, Risk-/Opportunity-Terme und Watchgraph-Gates.
- `config/watchgraph.yaml`: Regionen, Module, Buzzwords, Markt-/Risiko-Körbe.
- `keeper-clean/core_rules/senna_infoflow/`: Langzeitgedächtnis.

## Arbeitsregel

1. Monitor-Output zuerst lesen.
2. Output destillieren, nicht manuell parallel überwachen.
3. Relevante Erkenntnisse in `keeper-clean` speichern.
4. Schwächen zurück in Quellen, Regeln und Adapter übersetzen.
5. Re-run.

## High-Priority-Gates

High Priority nur bei mindestens einem Gate:

- direkter AXI0M/User-Yps/Question86/senna-infoflow-Bezug
- offizielle Quelle: Behörde, Vendor, Börse, Zentralbank, Notfall-/Wetter-/Geo-Institut
- zwei unabhängige belastbare Quellen
- aktive Ausnutzung / CISA KEV / Emergency Patch
- Katastrophe nahe Hauptstadt, Metropolregion oder kritischer Infrastruktur
- Marktbewegung bestätigt Narrativ

Social Media ist Rauch, nicht Wahrheit. LinkedIn nur über offizielle APIs. China nur mit Glaubwürdigkeits-Gate.

## Aktive erste Stufe

`sources.yaml` enthält jetzt lauffähige RSS-Knoten für:

- USGS Significant Earthquakes
- GDACS 24h / 7d / Orange-Red Earthquakes / Tropical Cyclones
- NOAA/NHC Atlantic, Eastern Pacific und Central Pacific Cyclone Feeds

## Adapter-Backlog

Für volle Hub-Leistung braucht `monitor.py` Adapter für GDELT, ReliefWeb, NASA FIRMS, CISA KEV JSON, NVD, FRED/World Bank/IMF/ECB, Bluesky/Mastodon/X, LinkedIn official APIs, SF Open Data/Eventbrite/Luma und Finance/market moves.

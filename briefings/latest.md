<!-- SENNA_QUALITY_GATE_START -->
## Coverage Warning

**Dieses Briefing ist kein repräsentatives Weltbild.** Es zeigt überlebende Signale aus konfigurierten öffentlichen Quellen.

- Coverage confidence: `low`
- Findings after quality gate: `0`
- Source errors: `8`
- Priority after gate: high `0`, medium `0`, observe `0`
- Failed sensor groups: `other`=6, `security`=1, `social`=1

> Score ist nicht Wahrheit. Er ist eine strukturierte Vermutung über ein unvollständiges Sensorfeld.

<!-- SENNA_QUALITY_GATE_END -->
# Senna Briefing

_Generiert: 2026-06-19T02:37:23+00:00_

## Kurzlage

Keine neuen relevanten Treffer aus den konfigurierten öffentlichen Quellen. 8 Quelle(n) hatten Abruffehler; Details stehen in latest.json.

## Priorität Hoch

Keine neuen Hochprioritäts-Treffer.

## Priorität Mittel

Keine neuen mittleren Treffer.

## Nur beobachten

Keine neuen Beobachtungssignale.

## Empfehlungen

- Keine direkte Handlung. Konfigurierte Quellen weiter prüfen.

## Erinnerungskandidaten

- Keine neuen langfristigen Erinnerungskandidaten.

## Quellenfehler

- `techinasia_feed` (rss): 403 Client Error: Forbidden for url: https://www.techinasia.com/feed
- `jpcert_english_alerts` (rss): 404 Client Error: Not Found for url: https://www.jpcert.or.jp/english/rss/jpcert.rdf
- `twcert_security_news` (rss): 404 Client Error: Not Found for url: https://www.twcert.org.tw/tw/lp-14-1-x.xml
- `github_search_japan_twitter_trend_rss_tools` (github_search): 422 Client Error: Unprocessable Entity for url: https://api.github.com/search/repositories?q=%28twitter+OR+x.com+OR+X%29+%28trend+OR+trending+OR+trends%29+%28RSS+OR+feed+OR+aggregator%29+%28Japan+OR+Japanese+OR+JP%29+stars%3A%3E5+pushed%3A%3E2025-01-01&sort=updated&order=desc&per_page=8
- `oecd_newsroom_macro` (webpage_check): 403 Client Error: Forbidden for url: https://www.oecd.org/en/about/newsroom.html
- `gdelt_macro_market_policy_rss` (rss): 429 Client Error: Too Many Requests for url: https://api.gdeltproject.org/api/v2/doc/doc?query=%28%22central+bank%22+OR+inflation+OR+%22rate+cut%22+OR+%22rate+hike%22+OR+bonds+OR+recession+OR+tariff+OR+sanctions+OR+oil+OR+shipping%29&mode=ArtList&format=rss&timespan=6h&maxrecords=50&sort=HybridRel
- `gdelt_politics_unrest_elections_rss` (rss): 429 Client Error: Too Many Requests for url: https://api.gdeltproject.org/api/v2/doc/doc?query=%28election+OR+protest+OR+strike+OR+coup+OR+parliament+OR+%22government+collapse%22+OR+sanctions+OR+unrest%29&mode=ArtList&format=rss&timespan=6h&maxrecords=50&sort=HybridRel
- `gdelt_initial_disruption_rss` (rss): 429 Client Error: Too Many Requests for url: https://api.gdeltproject.org/api/v2/doc/doc?query=%28wildfire+OR+%22forest+fire%22+OR+flood+OR+drought+OR+blackout+OR+%22port+closure%22+OR+%22supply+chain%22+OR+%22rail+strike%22+OR+%22pipeline+outage%22%29&mode=ArtList&format=rss&timespan=6h&maxrecords=50&sort=HybridRel

## Unter Beobachtung

Diese Lane ist absichtlich feed-unabhängig. Sie hält Themen sichtbar, auch wenn die Presse gerade woanders hinglotzt.

_Aktualisiert: 2026-06-19T02:37:23Z_

- **Japan X/Twitter Tech- und Event-Sturmfront** — `apac_japan_x_stormfront` / `active` / `routine`
  - Warum: Japan-X/Twitter kann Tech-, Popkultur-, Plattform- und Eventtrends früher zeigen als klassische Presse oder westliche Feeds.
  - Beobachten: Japanische Social-Velocity-Proxies, Hatena Hotentry IT, Google Trends Japan, GitHub-Suchen nach X/Twitter-Trend-RSS-/Aggregator-Tools, spätere stabile lawful X/RSS-Brücke.
  - Trigger: Japan, Tokyo, 日本, Twitter, X, trend, viral, Hatena, AI, security, outage, launch, anime, game, earthquake, social velocity
  - Update-Regel: Auch ohne neue Treffer mindestens im Routinebriefing anzeigen; bei bestätigter X/RSS-Brücke aktivieren.
  - Nicht tun: Keine fragile oder unrechtmäßige X-Scraping-Abhängigkeit als tragende Quelle behandeln.
  - Aktueller Feed-Signalabgleich: `0` Treffer
- **Südkorea Wahl-Infrastruktur und Protestvertrauen** — `south_korea_election_infrastructure_stress` / `active` / `routine`
  - Warum: Wahlverwaltungsfehler können sich in Infrastrukturvertrauenskrisen verwandeln; junge Protestkohorten und mögliche Zwangsräumung erhöhen Eskalationsrisiko.
  - Beobachten: NEC-Untersuchung, Polizeiräumung, Verletzte, offizielle Parlaments-/Behördenentscheidungen, Seoul-Protestzahlen, Desinformation/Cyber-/Leak-Bezug.
  - Trigger: South Korea, Seoul, Korea, election, ballot, NEC, protest, polling station, vote counting, forced dispersal, police, democracy, infrastructure trust
  - Update-Regel: Bei Reuters/AP/Yonhap/NEC-Bestätigung oder Räumungssignal hochziehen; sonst beobachtet lassen.
  - Nicht tun: Keine Wahlbetrugsnarrative ohne belastbare Belege verstärken.
  - Aktueller Feed-Signalabgleich: `0` Treffer
- **APAC Tech-/Social-Motoren außerhalb China** — `apac_tech_social_trend_mesh` / `active` / `routine`
  - Warum: Thailand, Taiwan, Philippinen, Vietnam, Korea und Japan sind eigenständige Trendmotoren; westliche Feeds sehen sie oft zu spät.
  - Beobachten: Regionale Trends, Tech-/Startup-Bewegung, Plattform-Ausfälle, KI-/Devtools, Halbleiter, Security, politische Plattformdynamik.
  - Trigger: Taiwan, TSMC, Thailand, Philippines, Vietnam, Korea, Japan, Singapore, Indonesia, India, startup, AI, platform, outage, security, developer tools
  - Update-Regel: In Routineupdates als Coverage-Achse behalten; bei Mehrquellen-Signal in OBSERVE/MEDIUM hochziehen.
  - Nicht tun: APAC nicht als China-Beifang behandeln.
  - Aktueller Feed-Signalabgleich: `0` Treffer
- **Global-South-Signalabdeckung Afrika und Südamerika** — `global_south_coverage_gap` / `active` / `routine`
  - Warum: Afrika und Südamerika sind bei Tech-, Infrastruktur-, Klima-, Energie-, Zahlungs- und Plattformthemen nicht zu unterschätzen; westliche Feeds blenden sie oft aus.
  - Beobachten: Tech-Ökosysteme, digitale Zahlungssysteme, Energie-/Netzausfälle, Klima-/Katastrophensignale, Plattformpolitik, Security, regionale Regulierung.
  - Trigger: Africa, Nigeria, Kenya, South Africa, Brazil, Argentina, Chile, Colombia, LATAM, fintech, mobile money, power outage, flood, drought, platform policy, cybersecurity
  - Update-Regel: Quellenabdeckung schrittweise ausbauen; Feed-Stille hier niemals als Weltstille werten.
  - Nicht tun: Afrika/Südamerika nicht nur über Katastrophenfeeds wahrnehmen.
  - Aktueller Feed-Signalabgleich: `0` Treffer
- **Mindanao nach dem Beben — Nachbeben, Wiederaufbau und regionale Stresspunkte** — `mindanao_post_quake_recovery_hotspots` / `active` / `routine`
  - Warum: Das Mindanao-Beben ist kein einzelnes Katastrophenereignis mehr, sondern ein dynamischer Entwicklungscluster: Nachbeben, Wiederaufbau, Versorgung, Preisregulierung, Immobilien, Versicherungen, Fischerei, Tourismus, Häfen/Logistik, Krankenhäuser und lokale Governance können sich über Wochen verschieben.
  - Beobachten: Nachbeben und Phivolcs-Lage, Glan und Sarangani-Landrutsche, General Santos City als Hafen-/Handels-/Versorgungsknoten, Krankenhäuser und Outdoor-Patientenversorgung, Trinkwasser/Sanitärversorgung, Lebensmittel/Baumaterial/Transportpreise, 60-Tage-Preisstopps und Marktumgehung, Versicherungs-/Schadensregulierung, Immobilienpreise/Mieten/Umsiedlung, Fischerei und Küstenökosysteme, Tourismus-Stornierungen, Schulen, Straßen/Brücken, Strom/Telekom, Häfen und maritime Infrastruktur, Wiederaufbauverträge, Korruptions-/Hilfsverteilungsrisiken, Landwirtschaft/Regenzeit/Monsoon, Küstenhebung/Tsunami-Folgen, mentale Gesundheit, Sicherheitslage und lokale Spannungen ohne Spekulation.
  - Trigger: Mindanao, Sarangani, Glan, Malapatan, Maasim, General Santos, GenSan, Davao Occidental, South Cotabato, SOCSCSKSARGEN, earthquake, aftershock, PHIVOLCS, tsunami, landslide, coastal uplift, hospital, water, sanitation, price freeze, insurance, real estate, rent, rebuilding, reconstruction, fisheries, fishery, tourism, port, airport, logistics, GSC, schools, bridge, road, power outage, telecom, aid distribution, monsoon
  - Update-Regel: In Routineupdates mindestens als Unter-Beobachtung-Thema führen; hochziehen bei M5+ Nachbeben, neuen Todes-/Verletztenzahlen, Preis-/Versorgungsengpässen, Hafen-/Flughafen-/Krankenhausausfällen, Versicherungs-/Immobilienmeldungen, Wiederaufbauvertragsskandal, Krankheitsausbruch, Regenzeit-Folgeschäden oder starker lokaler Protest-/Aid-Distribution-Dynamik.
  - Nicht tun: Nicht als einmalige Katastrophenmeldung abhaken; keine Armuts-/Chaos-Klischees über Mindanao; keine unbestätigten Gerüchte über Plünderung, Korruption oder Sicherheit verstärken; keine Immobilien-/Versicherungsclaims als Tatsache behandeln, bevor lokale oder belastbare Quellen sie stützen.
  - Aktueller Feed-Signalabgleich: `0` Treffer

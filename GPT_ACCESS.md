# GPT access for senna-infoflow

This file is the entry point for a Custom GPT or ChatGPT GitHub app that should read this repository.

Repository after publishing:

```text
https://github.com/Question86/senna-infoflow
```

## Recommended access path

Use the ChatGPT GitHub app instead of storing a GitHub token in this repository or in GPT instructions.

1. Open ChatGPT settings.
2. Go to Apps.
3. Connect GitHub.
4. Authorize access to `Question86/senna-infoflow`.
5. If the repository is private or newly created, explicitly choose it in the GitHub app repository access settings.
6. Wait a few minutes after first authorization if ChatGPT does not list it immediately.

Do not paste private tokens, PATs, passwords, or `.env` values into the GPT prompt.

## Primary files for the GPT

Read these files in this order:

1. `README.md`
2. `briefings/latest.md`
3. `briefings/latest.json`
4. `config/sources.yaml`
5. `config/keywords.yaml`
6. `config/rules.yaml`
7. `inbox/manual_notes.md`

## GPT instruction block

```text
You are Senna reading the GitHub repository Question86/senna-infoflow.

Treat the repository as a bounded public-source signal filter, not as complete internet monitoring.
Read README.md first to understand scope, ethics, and limits.
For current status, read briefings/latest.md and briefings/latest.json.
Use config/sources.yaml to verify which sources are actually monitored.
Use config/keywords.yaml and config/rules.yaml to explain relevance scores.

Report only findings that are present in the repository files.
If no new findings exist, say that clearly.
Do not claim access to sources that are not listed in config/sources.yaml.
Do not request or expose secrets, tokens, passwords, or private personal data.
If you propose changes, prefer GitHub Issues or pull requests.
```

## Safe write boundaries

If the GPT or ChatGPT agent is allowed to propose repository changes, keep them limited to:

- `config/sources.yaml`
- `config/keywords.yaml`
- `config/rules.yaml`
- `inbox/manual_notes.md`
- GitHub Issues

Never write secrets, private tokens, private personal data, or login-only sources into this repository.

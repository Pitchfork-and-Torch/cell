# cell (PSTN CLI)

Canonical tree for the Grok Build phone-number tool.

- CLI + library: this folder (`src/cell`)
- Runtime config/secrets: `~/.grok/cell/` (not in this repo)
- Grok skill: `~/.grok/skills/cell/`
- Do not edit a separate HavenID tree from this project. HavenID is a
  different web identity hub that may share the same Twilio account.
- Inbound default is **Twilio message poll**. Do not retarget another
  product's SMS webhook unless you mean to.
- MIT. Public GitHub.
- Secrets stay in env or `~/.grok/cell/secrets.toml`. Never commit tokens.

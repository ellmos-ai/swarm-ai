# Security Policy / Sicherheitsrichtlinie

[English](#english) | [Deutsch](#deutsch)

---

<a name="english"></a>
## English

### Supported Versions

| Version | Supported          | Notes |
| ------- | ------------------ | ----- |
| `0.1.x` | :white_check_mark: | Current active release branch (`master`) |
| `< 0.1.0` | :x:              | Historical experiments and archived snapshots |

### Local-First & Zero-Egress Architecture

`swarm-ai` is designed with a strict **local-first** and **least-privilege** security model:
- **Local Execution**: All swarm coordination logic, stigmergy marker databases (`swarm.db`, `chunks.db`), and runner orchestrations execute locally in user space without requiring elevated permissions (no root/admin required).
- **Zero-Egress Data Protection**: Local files, internal prompts, and private database states are never sent to third-party tracking services or external telemetry endpoints.
- **Fail-Closed Budgeting**: All parallel swarm routines enforce explicit token ceilings, call limits, and retry boundaries to prevent uncontrolled resource exhaustion.

### Reporting a Vulnerability

If you discover a potential security vulnerability in `swarm-ai`:

1. **Do NOT** open a public issue or discussion.
2. Submit a report privately via **GitHub Security Advisories**:
   - Navigate to [Security Advisories](https://github.com/ellmos-ai/swarm-ai/security/advisories/new)
3. Alternatively, contact the maintainers directly via email:
   - `security@ellmos.ai`
   - `support@lukasgeiger.com`
   - `lukas@open-bricks.org`

Please include in your report:
- A description of the vulnerability and affected components (e.g. runner, consensus, stigmergy API).
- Steps to reproduce or a minimal proof of concept (PoC).
- Potential impact and any proposed remediations.
- **Never** include private API keys, real credentials, or production data in your report.

---

<a name="deutsch"></a>
## Deutsch

### Unterstützte Versionen

| Version | Unterstützt        | Hinweise |
| ------- | ------------------ | -------- |
| `0.1.x` | :white_check_mark: | Aktueller Entwicklungs- und Release-Zweig (`master`) |
| `< 0.1.0` | :x:              | Historische Experimente und Archiv-Snapshots |

### Local-First- & Zero-Egress-Architektur

`swarm-ai` folgt einem konsequenten **Local-First**- und **Least-Privilege**-Sicherheitskonzept:
- **Lokale Ausführung**: Die gesamte Schwarmkoordination, Stigmergie-Datenbanken (`swarm.db`, `chunks.db`) und Runner-Orchestrierungen laufen lokal im User-Space ohne erweiterte Rechte.
- **Datenschutz & Zero-Egress**: Lokale Dateien, Prompts und Datenbankzustände werden zu keinem Zeitpunkt an externe Tracking- oder Telemetrie-Dienste übertragen.
- **Fail-Closed Budget-Schutz**: Alle parallelen Schwarm-Routinen erzwingen verbindliche Kosten- und Token-Obergrenzen sowie Limitierungen für API-Wiederholungen.

### Schwachstelle melden

Wenn Sie eine Sicherheitslücke in `swarm-ai` entdecken:

1. Eröffnen Sie bitte **kein** öffentliches GitHub-Issue.
2. Melden Sie die Schwachstelle vertraulich über **GitHub Security Advisories**:
   - [Sicherheitsbericht erstellen](https://github.com/ellmos-ai/swarm-ai/security/advisories/new)
3. Alternativ per E-Mail an das Sicherheitsteam:
   - `security@ellmos.ai`
   - `support@lukasgeiger.com`
   - `lukas@open-bricks.org`

Bitte geben Sie eine kurze Beschreibung, Schritte zur Reproduktion sowie betroffene Module an. Fügen Sie **niemals** API-Schlüssel oder private Zugangsdaten bei.

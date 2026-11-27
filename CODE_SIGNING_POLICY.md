# Code Signing Policy

Free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).

## Project & Artifact Scope
- **Project:** PS2 ISO Manager (`https://github.com/ZonalRipper/PS2-ISO-Manager`)
- **License:** MIT License ([LICENSE](LICENSE))
- **Signed Artifact:** `PS2-ISO-Manager.exe` (Windows standalone application built directly from this repository on GitHub-hosted Windows runners via `.github/workflows/release.yml`).
- Third-party open-source CLI tools (`bchunk`, `ziso`, `chdman`, `hdl_dump`, `pfsshell`) are verified against pinned SHA-256 hashes during CI packaging and are **not** signed individually.

## Team Roles & Approval
- **Committers / Maintainers:** Repository owner (`ZonalRipper`) and designated maintainers.
- **Reviewers & Signing Approvers:** Repository owner (`ZonalRipper`).
- Official signed releases are built exclusively from tagged commits on protected branches through GitHub Actions (`windows-latest`) with no self-hosted runners.

## Privacy Policy
PS2 ISO Manager does **not** collect, transmit, or store personal data, analytics, or telemetry.

Network requests are strictly limited to:
1. Checking `https://api.github.com/repos/ZonalRipper/PS2-ISO-Manager/releases/latest` for application updates and downloading verified release binaries over HTTPS from official GitHub domains when requested by the user.
2. Downloading PlayStation 2 game cover artwork from public community repositories (`Luden02/psx-ps2-opl-art-database` and `xlenore/ps2-covers`) only when the user enables artwork scraping.

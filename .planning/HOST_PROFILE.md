# Host Assurance & Capabilities Profile

- **Date**: 2026-09-18
- **Platform**: macOS (Darwin) + GitHub Actions runner (`ubuntu-latest`)
- **Conformance Level**: `C2-ROLES`
- **Command Execution**: PROVEN (Local shell command execution available via `run_command`)
- **Live Web Retrieval**: PROVEN (Playwright CDP, HTTP tools, GitHub API available)
- **Subagent Delegation**: PROVEN (`invoke_subagent`, `define_subagent` available)
- **Verifier Context**: SAME-CONTEXT REVIEW
- **Target Environments**:
  - Local macOS environment (residential Vietnamese IP, Playwright Chromium, port 9223 CDP)
  - Remote GitHub Actions runner (`ubuntu-latest`, Microsoft Azure datacenter IP, headless Chromium)

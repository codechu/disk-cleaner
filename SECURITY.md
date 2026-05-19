# Security policy

Disk Cleaner is a tool that can delete user files. For that reason we
take security vulnerabilities seriously.

## Supported versions

| Version | Supported |
|---|:---:|
| `main` branch | ✅ |
| Latest stable release (0.x) | ✅ |
| Older releases | ❌ |

Pre-1.0.0 period — only the latest release receives security fixes.

## Reporting a vulnerability

### Preferred path — GitHub Security Advisory (private)

Open a **private** advisory at
[github.com/codechu/disk-cleaner/security/advisories/new](https://github.com/codechu/disk-cleaner/security/advisories/new).
This way:

- The disclosure stays non-public until a fix lands
- A CVE can be requested automatically
- A coordinated fix can be worked out with the repo owners

### Alternative — Email

Write to `security@codechu.com` (PGP optional — key available at
[codechu.com/.well-known/security.txt](https://codechu.com/.well-known/security.txt)).

## Scope — what to report

**In scope:**

- **Arbitrary file deletion / overwrite** during the scan / cleanup flow
- **Permanent deletion** being triggered despite trash mode
- **Destructive operation triggering** via the Control API (blocked by design — a bypass is a bug)
- **Argument injection** in `pkexec` / `sudo` commands
- User data (Documents, Pictures, workspace) ending up in **auto-selection**
- **User-trace leakage** via `du_cache.db` / `snapshots.db`
- **External command triggering** via watchdog notifications

**Out of scope:**

- Third-party tools (apt, docker, npm) — their own vulnerabilities
- Users deleting their own data by mistake (not using dry-run, disabling trash mode)
- Social engineering

## Process

We review reports within a reasonable time on a best-effort basis.
Priority is set by severity, scope, and difficulty of the fix. No fixed
SLA is offered — this is an open-source project, not a contractual one.

Public disclosure is coordinated after the fix is released (together
with the reporter).

## Design invariants

The following are rules the codebase aims to uphold — a break is
treated as a security bug:

1. **Trash mode default** — The default for destructive operations is `gio trash`; permanent deletion requires an explicit user choice.
2. **Control API destructive-blocked** — `clean`, `purge`, `delete` cannot be triggered via the API. Only via a manual button in the GUI.
3. **Active-project protection** — Git trees that received a commit in the last 30 days are excluded from auto-selection.
4. **Process-aware skip** — Files currently in use (per `lsof`) are excluded from auto-selection.
5. **User-data exclusion** — Documents, Pictures, Videos, Music, Desktop, and workspace paths are never subject to automatic cleanup.
6. **No subprocess injection** — All `subprocess` calls use arg-list form (`shell=True` exception: only with constant string literals and [code-review approved](docs/I18N.md)).

A break in any of the above is treated as **critical**.

## Public disclosure

Once a confirmed fix is released:

- A summary is added to the CHANGELOG under the `### Security` category
  (with the reporter's name if they want credit)
- A GitHub Security Advisory is published
- If a CVE was assigned, its number is referenced

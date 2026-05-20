# Licensing — disk-cleaner

**Status:** Decided (2026-05-20). Review trigger: any change in
the Pro / commercial product plan, or first external contributor
signing a CLA.

## Decision

`disk-cleaner` is licensed under **GPL-3.0-or-later**. See
[`../LICENSE`](../LICENSE) for the full text and
[`../NOTICE.md`](../NOTICE.md) for third-party attributions.

## Why GPL-3, not MIT

- **Fork-and-close protection.** Under MIT a third party could take
  the codebase, polish it, and ship a closed-source competitor under
  a different name. GPL-3's copyleft requires any redistributed
  derivative to remain GPL-3, which materially reduces this risk.
  The "Codechu" mark itself is protected in Türkiye (TÜRKPATENT
  2012/93779, Class 42, through 2032) but Class 9 (downloadable
  software) and international jurisdictions are still open — see
  [FOLLOWUP item 1](../../codechu-internal/legal/FOLLOWUP.md). The
  license is the primary defence for the *code*; the trademark is
  the primary defence for the *name*.
- **GTK ecosystem norm.** GTK, GNOME, and most desktop apps that
  consume them ship under GPL-family licenses. GPL-3 fits the
  ecosystem's expectations and does not surprise packagers
  (Flathub, Snap Store, distro maintainers).
- **Compatible with our MIT libraries.** The codechu-* libraries
  remain MIT (a deliberate choice — see "Library licensing" below).
  MIT → GPL-3 combination is permitted; the resulting work is
  GPL-3.

## Why not source-available (PolyForm Shield / BUSL)

Premature. disk-cleaner does not yet have a meaningful user base
to monetise around. Starting source-available signals vendor
lock-in and caps adoption before the product has proven value.

If a paid "Pro" tier ships later, it will be a **separate codebase
or plugin** that communicates with the community core through an
IPC boundary (process separation). The Pro module can carry a
different license — proprietary EULA or PolyForm Shield — without
contaminating or relicensing the GPL community core. See
[lawyer KB §dual-licensing](../../codechu-internal-agents/agents/lawyer/kb/licenses/dual-licensing.md)
Pattern 2.

## Library licensing (codechu-*)

The 15 `codechu-*` libraries on which disk-cleaner depends remain
under **MIT**. Rationale:

- They are infrastructure (event bus, XDG paths, CLI framework,
  formatting helpers). The "fork-and-close" concern that motivates
  GPL for an end-user application does not apply at the
  infrastructure layer — these are not the differentiator.
- MIT maximises adoption, which is the primary value of an
  open-source infrastructure library.
- Mixing MIT libraries into a GPL-3 application is legally clean
  (compatible direction of flow).

## Consumer law disclaimer

GPL-3's no-warranty clause (§15-17) operates as a contractual
disclaimer. Under Turkish law:

- **For the free, open-source release**: Codechu is not acting as a
  "satıcı" under Law No. 6502 — there is no consumer contract —
  so the disclaimer holds in practice. Gross negligence and
  intent (TBK m. 115/1) remain non-disclaimable.
- **For a future paid "Pro" tier**: the GPL-3 disclaimer alone is
  **not sufficient**. A dedicated TR-compliant EULA (with 6502
  cayma carve-out, 12-point font, Tüketici Mahkemesi venue, and
  KVKK aydınlatma) will be required. See FOLLOWUP item _Pro EULA_.

## Reversibility

GPL-3 → more permissive (e.g. MIT/Apache) requires consent from
every copyright holder. While Codechu is the sole copyright holder,
that switch is mechanically possible. Once external contributors
land without a CLA, it becomes impractical.

If we plan to keep the option open of relicensing later, the choice
is:

- **DCO** (Developer Certificate of Origin) — current default for
  codechu-* libraries. Lightweight; does **not** grant Codechu
  relicensing rights.
- **CLA** (Contributor License Agreement) — Codechu retains the
  right to relicense future versions. Adds friction for
  contributors.

**Current stance**: DCO for libraries; for disk-cleaner, defer the
CLA decision until the first external contribution arrives. This
is logged in FOLLOWUP.

## Source-file headers

Source files do **not** yet carry SPDX headers
(`SPDX-License-Identifier: GPL-3.0-or-later`). Adding them across
the codebase is mechanical and is tracked in FOLLOWUP.

## References

- [GPL-3.0-or-later canonical text](https://www.gnu.org/licenses/gpl-3.0.txt)
- Lawyer-agent consultation, 2026-05-20 (this repo's chat log;
  permanent capture in lawyer KB changelog pending).
- [`../../codechu-internal/legal/FOLLOWUP.md`](../../codechu-internal/legal/FOLLOWUP.md)
  — open items (trademark, Pro EULA, EU representative, etc.).

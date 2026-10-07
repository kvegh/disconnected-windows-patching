# Design decisions history

## 2026-10-06 — Approved Nexus onboarding

Keep EULA acceptance in the Nexus installation playbook. Check the existing
acceptance state and use the supported API only when approval for the pinned
distribution is recorded in the encrypted configuration. This makes repeated
setup safe and avoids silently accepting terms for a future distribution.
Implementation: `4c83c87`. Both repository servers passed live onboarding.

## 2026-10-06 — Native conditional path validation

Validate Windows paths using Ansible's actual conditional parser and full-string
matching. Escaping that worked in a rendered expression failed in task assertions.
Implementation: `89cd9fc` (Nexus paths), `aac60dd` (internal transfer path).
The regression suite checks both forms of deployment input.

## 2026-10-06 — Targeted synchronization diagnostics

Expose a protected-by-default logging survey for external package publication,
so development failures can be diagnosed without changing the normal default.
Implementation: `62feaaf`. External synchronization and archive publication
passed live execution after approved onboarding.

## 2026-10-06 — Windows JSON array handling

Assign the converted JSON package array directly before counting and filtering it.
Wrapping the conversion in an array expression can retain a nested array on
Windows PowerShell and report one expected package instead of four. Keep all
manifest, package checksum and archive-path checks in place and report harmless
schema/count details when validation fails.
Implementation: `95cbd03`. Live import verification is in progress.

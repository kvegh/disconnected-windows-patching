# Focused review of 101 APME security observations

Assessment date: 2026-11-01. Delegated reviewer: `apme_security_101`.
Source: version **1.0.8**, executable revision
`399ad929fe3eda9cb75e60583f5160fe81ef7b98`. Scan:
`f3e526da-ed14-48b8-9eeb-023c4c764117`. This assessment examines the command,
transfer, privilege and path observations from that saved scan; it is not a
new full APME scan or final functional acceptance.

## Result

All **101 observations** have individual dispositions in the
[observation ledger](apme-security-observations.csv):

- **97 authored-project observations:** retain the existing implementation;
  no additional code defect with a worthwhile correction was demonstrated.
- **4 upstream observations:** integration-test fixtures in `microsoft.ad
  1.12.1`, outside this project's authored and invoked runtime content.
- **0 executable fixes:** no new wrapper, suppression, dependency, privilege,
  network or runtime change was justified to reduce the scanner count.

Version remains **1.0.8** because executable content is unchanged. A scanner
observing a parameter, a privileged operation or a mutable path is not by itself
proof of injection, excessive privilege or an unsafe write. The ledger records
the current resource boundary, preceding checks, practical benefit of changing
the task, and maintenance/regression cost for each observation.

The scope is the declared demo input contract: maintained deployment paths,
protected configuration and approved inventory are trusted inputs. Public launch
fields have the existing validation described in the ledger. This is not a
claim that arbitrary hostile operator configuration is safely sandboxed.

| Rule | Observations | Authored | Upstream |
| --- | ---: | ---: | ---: |
| R101 — Parameterized command | 46 | 45 | 1 |
| R104 — Source authorization | 5 | 5 | 0 |
| R105 — Parameterized outbound transfer | 2 | 2 | 0 |
| R106 — Parameterized inbound transfer | 5 | 5 | 0 |
| R108 — Privilege escalation | 25 | 23 | 2 |
| R114 — Parameterized file change | 14 | 13 | 1 |
| R115 — Parameterized deletion | 4 | 4 | 0 |
| **Total** | **101** | **97** | **4** |

## Why further code changes were not warranted

The 45 authored command observations use `ansible.builtin.command` with `argv`.
Inputs are separate arguments or protected JSON on stdin. The one intentional
activation-deadline shell program has fixed source and quoted positional
domain/MAC arguments. Replacing these interfaces with new wrappers or embedding
environment values in commands would not improve the reviewed trust boundary.
The [supporting-code guide](supporting-code.md) explains the specific platform
and artifact-format needs.

Transfers use declared inventory/manifest sources, immutable publication checks,
pinned vendor or locally computed SHA256 values, constrained package identifiers,
and same-server/feed assertions for Nexus asset URLs where applicable. Uploads
disable redirects; credential-bearing controller downloads prevent forwarding
Authorization on redirects. These are meaningful controls that the generic
parameterized-source warnings do not recognize.

The existing Nexus HTTP endpoints do **not** provide transport confidentiality.
Source authorization and byte integrity are different properties from TLS.
This assessment neither broadens the explicit WSUS HTTP exception nor certifies
Nexus traffic as confidential. A certificate/endpoint migration is a separate
scope and design decision, rather than an unverified cosmetic correction to
R104/R106.

Privileged operations are assessed in their actual context: system-libvirt
operations, host trust updates, local WSUS APIs and matching-principal async
status/cleanup. Read-only diagnostic tasks remain bounded even where the existing
hypervisor context is privileged. This does not assert that every task requires
root/SYSTEM on every possible platform, or that a full service-account access
audit was performed. Removing principals without equivalent target-side evidence
could break these operations. The separate service-account access audit was
owner-excluded; task-level operation context is assessed here.

Destructive clone operations require exact approved names/paths, the ownership
marker, expected disk references, no sharing, regular non-symlink storage and no
backing-image dependency. Temporary CA/profile/trust paths come from this run's
`tempfile` results and are protected and cleaned within their intended boundary.
Other staging paths come from maintained deployment configuration, rather than
untrusted remote file names. Adding another generic path framework would mostly
duplicate those controls.

## Validation and evidence limits

The existing focused offline checks cover ownership/target rejection, activation
topology and failure cleanup, AAP object-retirement boundaries, real verifier
transport behavior, archive/installer hashes and path-traversal rejection.
They exercise the maintained production assertions, parsers and clients with
fixtures; they do not run real libvirt, Windows, WSUS, Nexus or LDAP operations.

Run from the repository root with the externally prepared private review
configuration and approved collections:

```bash
PYTHONPATH=tests ANSIBLE_DEPRECATION_WARNINGS=true python3.12 -m unittest -v \
  test_windows_teardown_scope test_windows_activation_domain \
  test_windows_activation_flow test_active_directory_migration \
  test_active_directory_verifier test_chocolatey_export \
  test_offline_chocolatey_package
python3.12 -m ansiblelint --profile production --strict --offline
```

Validation used actual local ansible-core **2.16.19** and Python **3.12.14**.
The recorded focused run passed **64 tests without skips in 13.578 seconds**.
Strict production lint passed
**116 processed files with zero rule failures/warnings**. The vendor Python
`crypt` warning and offline dependency-install notice remain visible in the raw
evidence; neither was hidden by this review.

The first run's inline result was repeated once to retain owner-only raw logs
and exit-code metadata for the parent's independent verification. Protected
evidence filenames are `apme-security-101-tests.log`,
`apme-security-101-lint.log` and `apme-security-101-validation.json` in the
existing private review artifacts, outside Git. Ledger coverage checks verify
that every saved `(rule_id, file, line)` key appears exactly once.

This result does not clear the other **754 APME observations**, establish that
the failed dependency backend audited anything, or replace the owner's combined
functional test. Existing demo exceptions remain scoped as recorded in the
[requirements/deviation record](review-requirements-and-deviations.md).

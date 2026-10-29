# Code review record — 2026-10-29

**Incomplete review record; no claim of full policy compliance or final functional
acceptance.** The owner is responsible for the combined functional test. This
document records the source assessment, available evidence and remaining gaps.
It is not the successful `Code_Review_YYYY-MM-DD.md` required after acceptance.

## Scope and exact revisions

- Reviewer: Codex. Readability, simplicity and unnecessary complexity were
  assessed by this agent. Claude/Gemini reviews announced by the owner have not
  been performed here; no independent consensus is claimed.
- Assessed executable revision: version **1.0.8**, implementation
  `399ad929fe3eda9cb75e60583f5160fe81ef7b98`. Later documentation commits do not
  establish runtime evidence for different executable content.
- Core functional evidence: version **1.0.7**,
  `da6086ecbeb3183b1bd31da32a2df6cbdfd19539`.
- Policy: `Agent_generated_code_review` commit `e45b49b`.
- CoP guide: `fb5fcd6f03c544909dbad352a352b421c41d7203`; upstream HEAD
  rechecked unchanged on this date.
- Runtime: actual vendor AAP EE, ansible-core **2.16.19**, Python **3.12.14**.
  Exact collection pins and observed image digests are in the
  [requirements record](docs/review-requirements-and-deviations.md#scope-and-baselines).
- Environment: prepared-image KVM/libvirt Windows demo, core Server 2022/2025
  managed nodes and the included Server 2025 AD extension. This does not assert
  support for arbitrary hypervisors, editions, locales or production hardening.
- Complete current source/CaC/protected-configuration release provenance has
  not been established. Sensitive environment inputs and raw job evidence remain
  in protected storage outside this repository.

## Requirement and source assessment

The [requirements/deviation record](docs/review-requirements-and-deviations.md)
accounts for all 15 policy sections. The
[CoP directive trace](docs/review-cop-directives.csv) contains 310 section,
bullet and contextual-example entries across all 13 areas, each with a pinned
source location, disposition and assessment. Unresolved outcomes are retained;
an index or a scanner result is not a blanket pass.

The [quality assessment](docs/review-quality-assessment.md) gives explicit source
verdicts for readability, simplicity and avoiding overengineering, with file
groups, reasons for necessary complexity and limitations. These are source
judgments, not conclusions derived from test counts. No additional generic
framework or role/collection migration was warranted solely by those criteria.

## Confirmed corrections and verification

| Correction | Implementation and evidence |
| --- | --- |
| Supported Ansible run-as and native file handling | `4fdfd7f`; focused implementation and rationale recorded in decision history. |
| Regression harness hid Ansible deprecations and could omit required update operations | `bb7abd7`; warnings enabled, vacuous-success paths rejected in regressions. |
| Deprecated IIS modules and collection/core incompatibility | `09f570f`; native `microsoft.iis` replacement, core-compatible Chocolatey pin, native forest module and strict lint fixes. IIS/WSUS export job 2618 passed in 151.092 seconds. |
| Two PowerShell mock failures | `9a76208`; fixture scope and hash-module autoload isolation corrected. Normal protected-output regression job 2627 passed all six suites on both managed servers in 37.662 seconds. |
| Actual deployment usernames in public presenter guides | `7c76036`; current guides use protected-prefix placeholders. Historical usernames were subsequently accepted by the owner; no history rewrite is required. |
| Broad controller defaults loaded an unused deprecated plugin; workflow omitted a required protected-output answer | `386026c`; defaults scoped to used modules and required workflow input supplied; syntax/configuration validation passed. |
| AD verifier accepted unsafe target roots and followed HTTP redirects | `399ad929fe3eda9cb75e60583f5160fe81ef7b98`; require HTTPS platform root and reject redirects. Tests exercise the actual urllib handler chain with synthetic responses and prove only one request occurs. No live credential forwarding was attempted. |
| Browser examples still showed obsolete IIS usage | Same 1.0.8 implementation; examples corrected and supporting JavaScript rationale linked. Browser regressions passed. |

Scope/preservation safeguards and documentation improvements are recorded
separately in the decision history; they are not presented as invented defects.
APME observations were not treated as a finding quota or blindly auto-applied.

## Validation results and their limits

| Check | Result and scope |
| --- | --- |
| Python regressions, 1.0.8 | **109 passed**, no skips, 21.254 seconds. Actual local target core 2.16.19/Python 3.12.14. The vendor `crypt` warning remains visible. |
| Browser regressions, 1.0.8 | **14 passed**, no skips. Process illustration only. |
| Strict production lint, 1.0.8 | **Passed**, 116 processed files, zero rule failures/warnings; ansible-lint 26.8.0. Offline dependency-install notice retained in raw output; preinstalled pins were available. |
| Gitleaks | Current-tree and prior Git-history checks reported zero pattern matches. This does not establish arbitrary identifier privacy or full platform security. |
| APME, 1.0.8 | Scan `f3e526da-ed14-48b8-9eeb-023c4c764117`: 855 final observations. All six backend calls returned; dependency auditing failed internally. Backend counts and dispositions are in the requirements record. |
| Supplemental Python dependency audit | 25 real PyPI distributions in an isolated target session, excluding seven synthetic collection records. Upstream package advisories require separate applicability assessment against the vendor EE. |
| Core functionality, 1.0.7 | **PASS within the core scope:** workflow 2682 completed all 21 stages, including provisioning, repository setup/content transfer, managed patching, baseline application deployment and upgrades. Started 2026-10-27 19:06:56 UTC; finished 23:15:01 UTC; 4h 8m 5s. |
| Original combined workflow, 1.0.7 | Workflow 2742: all 21 core stages passed, but overall execution failed. AD creation job 2749 never started because project update 2750 failed retrieving hub collection metadata. Six later AD stages did not run. The prerequisite sync retry 2769 succeeded with unchanged sources/pins; that does not prove AD deployment. |
| Full combined functionality, 1.0.8 | **Not confirmed.** No full Windows/AD pass is claimed. The owner handles this test separately. |
| CaC repeat application | Exercised native configurators reported zero changes. Complete fresh restoration and repeat verification of all current objects are not demonstrated. |

Reproducible offline entry points, using the externally prepared target
environment and private configuration where required:

```bash
ANSIBLE_DEPRECATION_WARNINGS=true python3.12 -m unittest discover -s tests -v
python3.12 -m ansiblelint --profile production --strict --offline
node --test demo/tests/scenario.test.cjs demo-with-aap/tests/*.test.cjs
gitleaks dir --redact .
```

The [test guide](tests/README.md) explains what the Python/PowerShell/browser
suites prove and what they cannot prove. APME's tool environment is separate
from the target AAP runtime.

## Deviations, conflicts and remaining gaps

Accepted dispositions D1–D16 in the requirements record include compatible
legacy names, coherent task includes, documented supporting code, useful existing
tests and owner-directed main-only work. Each identifies the reason and revisit
condition. On 2026-10-29 the owner explicitly accepted:

- The existing lab WinRM server-certificate-validation exception, documented.
- The existing WSUS HTTP transport, documented.
- Historical deployment usernames, with no history rewrite required. This is
  not permission to expose passwords, tokens or other secrets.
- Skipping additional idempotency and CaC reconstruction verification for this
  review. Existing evidence is retained; no unperformed verification is reported
  as passed.
- Retaining current mutable release references instead of introducing locking;
  existing recorded source/image identifiers remain scoped evidence.
- Retaining existing review checks, Pages CI and GitHub protection without
  introducing additional automated Ansible/pre-commit/CI gates.

Conflicting naming, comments, historical Jinja, native-module preference and Git
workflow guidance are resolved explicitly in the
[conflict table](docs/review-requirements-and-deviations.md#conflicting-guidance-and-chosen-approaches).
These choices preserve existing interfaces and the supported AAP runtime instead
of introducing cosmetic breakage or unsupported upgrades.

Owner-skipped gaps include additional idempotency and complete CaC reconstruction
verification, release-reference locking and additional CI gates. Remaining open
questions include APME dependency-backend coverage/vendor warning
disposition; full image/SBOM and advisory applicability assessment; CIS control
assessment; and unverified rotation/access-audit/rollback practices. These are
not automatically confirmed playbook defects. Full functional evidence remains
the owner's responsibility. Nothing here reports an unperformed check as pass.

## Proportionate recommendations

| Recommendation | Benefit, cost and priority |
| --- | --- |
| Resolve APME's synthetic-package audit handling | Necessary for a reliable claim that this backend completed. Separate collection metadata from actual PyPI requirements and retain explicit audit failures. Tooling work; do not change playbooks or fetch collections from PyPI to satisfy it. The supplemental Python audit remains scoped evidence. |
| Consider native AD identity modules during a future identity change | Optional maintainability comparison. Native user/group/OU modules already exist; a migration must preserve ownership, retirement and administrator-added members and demonstrate simpler behavior with live evidence. Moderate migration/regression cost; no replacement framework added now. |
| Consider a shared WSUS module only if separate consumers emerge | Optional reuse opportunity for a narrow server-side API gap. Check maintained/certified content first. A module/collection adds interface, test, release and support work; low priority for this single demo. Publish any future collection release to private hub. |
| Consider PowerShell static analysis and targeted runtime compliance tooling | Optional additional tools can cover Windows-language style or selected host controls beyond present tests. Select rules/profile, compare overlap and obtain installation approval if needed. They were not run and cannot be credited as evidence. |

The source review has produced concrete corrections and documented judgments.
This record does not assert that every requirement has passed or that the
repository has completed final acceptance.

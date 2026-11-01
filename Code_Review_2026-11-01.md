# Code review closeout — 2026-11-01

**Agreed code-only review closed, with documented deviations and deferred
verification.** The owner requested this report update to finish the agent's
review work. No further confirmed source defect remains on the current review
list. This does not establish that every guideline conforms or every scanner
observation was individually cleared.

**Full functional acceptance is not confirmed.** The combined Windows/AD test
belongs to the owner. This report records its missing evidence explicitly; it
is not the successful end-to-end acceptance certificate described by the full
review policy. The [earlier incomplete record](Code_Review_2026-10-29_INCOMPLETE.md)
remains as historical evidence.

## Scope and exact baseline

| Reference | Reviewed baseline |
| --- | --- |
| Executable source | Version **1.0.8**, `399ad929fe3eda9cb75e60583f5160fe81ef7b98`; subsequent changes through this closeout are documentation only |
| Reviewer | Codex, including the delegated 101-observation security assessment and its parent verification |
| Review policy | `Agent_generated_code_review` at `e45b49b` |
| Whole CoP guide | `fb5fcd6f03c544909dbad352a352b421c41d7203`; upstream HEAD last checked unchanged on 2026-10-29 |
| Red Hat reference | Local AAP 2.7 Develop and Secure guides, applied against the actual deployed runtime |
| Actual runtime | Vendor AAP EE: ansible-core **2.16.19**, Python **3.12.14**; controller API reports **4.8.8** |
| Environment | Prepared-image KVM/libvirt demo, four core Windows clones, Server 2022/2025 managed nodes, WSUS/Nexus and application stages, plus the included Server 2025 AD extension |

The [requirements record](docs/review-requirements-and-deviations.md#scope-and-baselines)
contains exact collection pins and observed EE digests. Published releases are
consumed from private automation hub; no collection is vendored and no custom
collection or EE was introduced. Complete immutable source/CaC/protected-input
release provenance has not been established. Mutable references are explicitly
retained under D15.

Other hypervisors, arbitrary Windows editions/locales, production hardening and
Windows/AD CIS host-compliance assessment are outside the declared review scope.
Deployment code and code-level credential, command, path and failure handling
remain included. An untested environment is not reported as incompatible.
Sensitive inputs and raw evidence remain in protected storage outside Git.

## Requirements and source quality

All **15 policy sections** have an outcome in the
[requirements/deviation record](docs/review-requirements-and-deviations.md).
The [CoP trace](docs/review-cop-directives.csv) covers all **13 areas**, with
**310** section, bullet and contextual-example entries: 36 pass, 162 accepted
deviation and 112 justified not applicable. These are trace entries, not 310
independent tests. No CoP entry remains undecided; accepted or skipped checks
are not counted as verified conformance.

The [source-quality assessment](docs/review-quality-assessment.md) explicitly
records **readability: pass with limitations; simplicity: pass with documented
deviations; no overengineering: pass for the assessed implementation**. These
judgments cover deployment playbooks, includes, supporting assets, tests and
browser walkthroughs. They come from source assessment, not test counts. No
human sign-off or independent Claude/Gemini review is claimed.

The cleanup did make practical adaptations: native IIS and AD forest/reboot
modules, compatible collection versions, clearer lint-compliant YAML, short
linked rationale comments, and removal of an unused 435-line WinRM script.
Existing coherent includes, safety guards and bounded supporting code remain;
another framework or cosmetic refactor would add cost without demonstrated
benefit. The [supporting-code guide](docs/supporting-code.md) records reasons
for retained Python, PowerShell and command operations and native alternatives.

## Confirmed corrections

| Change | Implementation and verification |
| --- | --- |
| Supported run-as and native file handling | `4fdfd7f`; replaced avoidable shell operations with supported Ansible behavior |
| Regression harness warning visibility and update checks | `bb7abd7`; enabled deprecation warnings and rejected missing required update operations |
| Deprecated IIS modules and incompatible dependencies | `09f570f`; native IIS/forest modules, compatible Chocolatey pin, strict lint fixes, rationale comments and legacy script removal; IIS/WSUS export job 2618 passed |
| PowerShell test fixture defects | `9a76208`; corrected mock scope and hash autoload isolation; all six suites passed on both managed servers in job 2627 |
| Current public deployment usernames | `7c76036`; presenter guides now use placeholders; historical usernames subsequently accepted by the owner |
| Overbroad controller defaults and missing protected-output input | `386026c`; scope defaults to used modules and supply the required workflow answer; syntax/configuration validation passed |
| Unsafe AD verifier target/redirect behavior | `399ad929fe3eda9cb75e60583f5160fe81ef7b98`; require HTTPS platform root and reject redirects; offline tests exercise the actual urllib handler chain |
| Obsolete illustrative IIS examples | Same 1.0.8 change; examples corrected and browser regressions passed |

The [decision history](design_decisions_history.md) explains the reasons and
evidence. Scanner observations were not treated as a finding quota; the later
101-observation assessment justified **zero additional executable fixes**.

## APME disposition

Saved scan **`f3e526da-ed14-48b8-9eeb-023c4c764117`**, against 1.0.8 on
2026-10-29, used pre-release APME
`9c4372f79a8b537865040cea17cf9db7659614ad`. Its **855** final observations
are accounted for as follows:

| Group | Count | Final review disposition and limit |
| --- | ---: | --- |
| Command, transfer, privilege and path observations | 101 | Individually assessed: 97 authored operations retained with existing controls and four upstream fixtures excluded. [Per-case ledger](docs/apme-security-observations.csv) and [rationale](docs/apme-security-triage.md). No worthwhile additional correction demonstrated. |
| Possible undefined variables, L039 | 321 | **Owner-deferred, D23.** Not individually cleared or guaranteed at runtime. The native static parser does not decrypt Vault; that limitation does not explain every observation. |
| Wrong runtime target, parser/semantic mismatch or informational rules | 62 | Group-level disposition: not demonstrated current-source defects. Future core 2.19+ trust-model advice does not target core 2.16.19; a connection option is not a removed fact; AAP users are not OS users; literal-script text is not a YAML duplicate-key failure. |
| Style, structure and necessary-operation advice | 371 | Group-level proportionality disposition under D1–D9 and the source-quality assessment. Preserve stable names, readable valid expressions, coherent includes, required state/connection changes, visible proof summaries and appropriate community modules. No mechanical rewrite solely to reduce scan counts. |
| **Total** | **855** | Group-level assessment of the latter 433 is not a claim of 433 individual reproductions or fixes. The 321 deferred warnings remain unverified. |

The [requirements record](docs/review-requirements-and-deviations.md#tool-results-and-limits)
gives the grouped rule IDs and reasons. No blanket suppression or automatic
patch was applied. APME also reported a formatter-idempotence error; proposed
formatter edits were not used.

Five backends delivered usable results: Native 785, OPA 58, Ansible 1,
collection-health 11 and Gitleaks 0. The sixth, **dependency audit, failed
internally** despite returning zero observations. Synthetic bookkeeping records
for seven Galaxy collections were incorrectly looked up on PyPI. A separate
audit covered 25 real PyPI distributions in an isolated session, but that is
not a complete vendor EE or collection vulnerability assessment.

For this code-only closeout, the reviewer records that tooling coverage gap as
**D24**, under the owner's proportionality requirement. It remains an incomplete
backend, not a clean audit. Revisit the APME integration when complete dependency
coverage is required; no project rewrite or package installation is justified
merely to make this tool return cleanly.

The vendor core's Python **`crypt` deprecation warning** is separately recorded
as **D25**. No authored direct `crypt` call was found; warnings stay visible and
the supported runtime is retained. This is a reviewer disposition for the
scoped closeout, not a claim of zero warnings or an explicit owner approval of
each dependency. Reassess when the supported EE/core/Python changes. No vendor
patch, independent core upgrade or warning suppression was introduced.

## Functionality confirmation and evidence limits

| Check | Recorded result |
| --- | --- |
| Full offline Python suite, 1.0.8 | **109 passed**, no skips, 21.254 seconds, target core 2.16.19/Python 3.12.14 |
| Browser checks, 1.0.8 | **14 passed**, no skips; validates the process illustration, not deployed AAP |
| Strict production lint | **Passed**, 116 files, zero rule failures/warnings; offline install notice retained |
| Focused security follow-up, 2026-11-01 | **64 existing tests passed**, no skips, 13.578 seconds; strict lint passed 116 files; Gitleaks zero matches |
| Earlier PowerShell runtime regressions | Job **2627**, all six suites on both managed servers passed in 37.662 seconds, on its recorded earlier revision |
| Earlier IIS/WSUS export | Job **2618** passed in 151.092 seconds, on its recorded earlier revision |
| Secret scanning | Current tree and earlier Git-history scans reported zero pattern matches; this does not prove arbitrary identifier privacy |
| Native CaC repeat application | Exercised configurators reported zero selected-object changes; complete current restore not demonstrated, owner-skipped D14 |
| Core functional workflow | **2682 passed all 21 stages**, version 1.0.7, `da6086ecbeb3183b1bd31da32a2df6cbdfd19539`; 2026-10-27 19:06:56–23:15:01 UTC, **4h 8m 5s** |
| Original combined workflow | **2742 failed overall**, version 1.0.7; all 21 core stages passed. AD creation 2749 never started because project update 2750 failed retrieving hub metadata. Six later AD stages did not run. Unchanged prerequisite sync retry 2769 passed; that does not prove AD deployment. |
| Complete combined Windows/AD functionality, current 1.0.8 | **Not confirmed; owner-owned.** No complete 29-stage pass or current runtime acceptance is claimed. |

Reproducible offline commands and their prerequisites remain in the
[earlier evidence record](Code_Review_2026-10-29_INCOMPLETE.md#validation-results-and-their-limits)
and [test guide](tests/README.md). This closeout changes documentation only;
behavior suites and live workflows were not repeated for it.

## Accepted limits, conflicting guidance and follow-up

**D1–D25** in the requirements record identify the choice, benefit/cost rationale
and revisit condition. Important boundaries are the legacy names and documented
supporting code; owner-directed main-only work; accepted WinRM certificate
validation and WSUS HTTP exceptions; historical usernames; skipped additional
idempotency, CaC restoration, release locking, CI and rollback checks; excluded
service-account and vendor-image assessment; accepted network boundaries;
code-only CIS scope; deferred variables; and the two tooling/vendor limitations
above. Rotation remains umbrella Beads task **`bead-wd-8ee`**.

Existing Nexus HTTP has no TLS confidentiality. Hash/source controls do not
provide that property, and the explicit WSUS exception is not broadened to
other services. Production-grade transport security is not certified here.

The [conflict table](docs/review-requirements-and-deviations.md#conflicting-guidance-and-chosen-approaches)
records why stable legacy entry points override cosmetic naming changes, short
linked rationale comments override blanket comment avoidance, supported runtime
syntax overrides historical EL7 examples, native modules are preferred while
documented API/format gaps retain supporting code, simple includes/std-library
tests avoid unnecessary frameworks, and owner-directed main overrides a PR
process. Separating source closure from the owner's functional test preserves
the failed/missing test evidence rather than relabeling it a pass.

Optional future improvements remain proportionate: correct APME's synthetic
package handling when its full audit is needed; compare native AD identity
modules during a real identity change; consider a WSUS module only with separate
consumers; evaluate additional PowerShell/static tooling only for a defined
gap. None was implemented or credited as evidence.

**Conclusion:** the agreed agent code-review work is closed with the recorded
deviations and deferred checks. This report makes no full-policy-conformance,
CIS-compliance, complete-dependency-audit or combined-functional-pass claim.

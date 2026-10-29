# Review requirements, deviations and remaining evidence

Status date: 2026-10-29. **Review incomplete; no final acceptance.** This record
applies the [review policy](https://github.com/kvegh/Agent_generated_code_review/blob/e45b49b/README.md)
at `e45b49b` to this repository. It records source judgments separately from
runtime evidence and identifies unverified requirements instead of treating them
as passes. The [quality assessment](review-quality-assessment.md) contains the
explicit readability, simplicity and overengineering judgments.

## Scope and baselines

The supported implementation is the prepared-image KVM/libvirt Windows demo:
four core clones, Server 2022/2025 managed hosts, WSUS/Nexus content transfer and
application deployment. The included AD extension adds one Server 2025 domain
controller and uses an existing separate test AAP. Other hypervisors, arbitrary
Windows editions/locales, production hardening certification and universal
portability are outside this implementation and test environment. An untested
scenario is not reported as incompatible.

The original combined AAP workflow has 29 stages: 21 core and eight AD. The
owner requires one complete execution for acceptance. A successful core run and
separate AD jobs do not replace that test. A complete combined pass remains
required for acceptance.

| Reference | Recorded baseline |
| --- | --- |
| Source with current core functional evidence | Version 1.0.7, `da6086ecbeb3183b1bd31da32a2df6cbdfd19539` |
| New source changes | Version 1.0.8; exact implementation commit in the dated record |
| CoP guide | `fb5fcd6f03c544909dbad352a352b421c41d7203`; upstream HEAD rechecked unchanged on 2026-10-29 |
| AAP reference | AAP 2.7 local Develop and Secure guides; local documentation edition and actual EE are different kinds of evidence |
| Actual EE runtime | `ansible-core 2.16.19`, Python `3.12.14`; controller API reports `4.8.8` |
| EE image | Vendor-supported RHEL 9 AAP image; deployed reference uses `latest`, an immutability gap |
| Observed RepoDigests | `sha256:382c82a692175ba73dd034cea9961ff146ca3e2c115021919bf52d41f2454b3c`; `sha256:d97a6fc9c34132bfddf5c8f0db93a24fea67ed3db2094d15f78d7f4eba724f1f` |
| Collection pins | `ansible.windows 3.8.0`, `community.windows 3.3.0`, `chocolatey.chocolatey 1.5.3`, `microsoft.iis 1.3.0`, `microsoft.ad 1.12.1`, `ansible.controller 4.8.11`, `ansible.platform 2.7.20260930` |

Both RepoDigests are recorded as observed; this review does not guess which
represents an image index versus platform manifest. Private evidence contains
installed versions, hub artifact metadata/checksums and protected environment
inputs. Those inputs, secrets and raw controller exports are not published here.
No new custom EE or collection was created.

## Policy coverage

An unresolved outcome means a real evidence gap or an undecided exception. It
does not automatically mean an observed playbook failure.

| Policy section | Outcome and evidence |
| --- | --- |
| 1. Whole CoP and evidence-based findings | All 13 areas are accounted for below and in the directive trace. Examples and historical qualifications are interpreted in context. No finding quota; automated observations are investigated before being called defects. Unresolved items remain explicit. |
| 2. Red Hat and CIS guidance | Local AAP Develop guidance informed native content, dependency declaration and execution choices; Secure guidance informs protected credentials/trust. No CIS host compliance claim: benchmark/profile/control assessment has not been completed. This remains a security-assessment gap. |
| 3. Actual AAP core; no deprecations | Deprecated IIS usage replaced and compatible pins selected. Warnings remain enabled. Core 2.16.19 imports Python's deprecated `crypt` in offline tests; vendor dependency disposition remains unresolved. Newer tooling core is not the deployment baseline. |
| 4. Readability, simplicity, naming, comments | Explicit source assessment completed in the linked quality document. Naming documented in README; compatibility deviations retained. Comments explain unusual operations and link to supporting-code reasons. No human readability sign-off is required. |
| 5. Native and certified content | Native IIS, AD forest, Windows package/service/file and AAP modules used where suitable. Foreign code reasons and remaining alternatives are documented. Exact hub releases were checked: Windows/controller/platform pins in the certified channel; the four other pins in the community channel. A namespace alone does not establish certification. |
| 6. Idempotency and recovery | Deterministic artifacts, bounded update/network/async recovery and cleanup are assessed. Native configurator repeat applies reported zero changes. Provisioning, synchronization and guarded deletion have operational semantics; no universal zero-change or first-run check-mode claim. Full fresh-environment repeat/convergence evidence remains incomplete. |
| 7. Sensitive configuration and security | Current protected inputs use Vault/AAP/private inventory and protected temporary files/output. Gitleaks is used, but cannot prove absence of arbitrary environment identifiers. The owner accepted the existing WinRM certificate-validation and WSUS HTTP lab deviations and closed the historical-username concern on 2026-10-29 (D10–D12). Rotation and full access review remain unverified; these are distinct from observed code defects. |
| 8. Private hub and collection source | Exact published releases consumed from private hub; no runtime collection source vendored. Requirements files declare dependencies. Custom collection build/publication rules are not applicable because none is authored. |
| 9. AAP and EEs | Normal job templates/workflows exercised the deployed vendor EE. No custom EE build is needed. Shared mutable image reference and complete vendor image/SBOM assessment remain gaps; changing a shared EE would affect other projects and was not done. |
| 10. CaCable | Declarative native configurators exist and repeat-apply checks passed for exercised objects. Full reconstruction of all current projects, templates, surveys, workflow and credential references on a fresh AAP has not been demonstrated. An older core export does not close this requirement. |
| 11. Speed | Core run 2682 took 4h 8m 5s; combined run 2742 ended after 4h 18m 21s. Independent stages retain workflow concurrency; waits and safety checks serve specific dependencies. No unsupported speedup or RAM root-cause claim is made. |
| 12. Strict lint and APME | Production lint and six backend attempts recorded. APME dependency audit is incomplete despite returning zero observations; other counts require triage, not automatic edits. See backend table. |
| 13. Smoke and complete end-to-end | Provisioning/native connectivity, core patch/application stages and targeted regression jobs passed on recorded revisions. Combined workflow 2742 failed before AD creation; a complete combined pass is still missing. New 1.0.8 runtime validation is pending. |
| 14. Review cycle and report | Findings fixed in batches with focused tests. This iteration is incomplete; the new transport fix requires the restarted review and full functional cycle. An explicitly incomplete dated record must not impersonate the successful report required by policy. |
| 15. Documentation | README, TLDR, decision history, guides and Pages walkthrough describe the implementation and scope. Version 1.0.8 corrects illustrative IIS snippets and historical/current evidence wording. Walkthrough state is illustrative, not live telemetry. |

## CoP coverage and interpretation

The [directive trace](review-cop-directives.csv) records source locations and
dispositions, including bullet-level entries and contextual examples. Context
entries are not extra mandatory controls. A section's unresolved outcome is
retained for its examples where the same evidence is missing; no blanket pass is
inferred from having indexed the guide.

| CoP area | Application and disposition |
| --- | --- |
| Structures | AAP composes stages; small included task files share operations. Accept playbooks/includes instead of introducing a role hierarchy solely for packaging. The guide itself qualifies its example hierarchy. D1. |
| Naming conventions | README defines snake_case inputs/new YAML, imperative names and legacy interfaces. Preserve numbered/hyphenated entry points and published AAP labels/resource keys. D2. |
| Roles | No authored deployment roles. Role packaging, defaults, providers, argspec and Molecule-specific layout do not apply as role requirements. General principles of interface validation, ownership, convergence, bounded platform support and documentation still inform the playbook assessment. |
| Collections | No authored collection. Consumption rules apply: exact pins, private hub, no vendored runtime content. A dedicated source repo/publication would be needed if future custom content is justified. |
| Playbooks | Native named tasks/includes, no mixed role/task orchestration. No fine-grained tag framework is needed. Operator success/evidence summaries remain visible; routine diagnostics use protected/default logging. D4. |
| Inventories | AAP inventory and encrypted environment inputs provide the lab's desired state; runtime facts describe observed state. Managed plays target inventory groups. Flat exported inventory, Vault include_vars, scoped defaults and survey extra vars are retained for this bounded AAP interface. D3/D5; no claim that this exactly matches the CoP directory example. |
| Plugins | No shipped custom Ansible plugin. Temporary mock plugins are offline test scaffolding. General clarity/documentation principles assessed; existing unittest, compact Python functions and partial type hints are retained rather than undertaking a new typing/test-runner migration. D6. |
| Coding style | Strict production lint, named tasks, FQCNs, YAML arguments, explicit includes and casts are used. Linked comments override the CoP's avoid-comments preference. Jinja equality is supported by the actual runtime. Quote/dot-lookup/data-serialization preferences and meaningful immediate handlers are proportionate deviations, not automatic defects. D3/D4/D7. |
| AAP configuration | Native declarative configurators satisfy parts of the intent without adopting a new infra dispatch framework. Complete fresh reconstruction, consolidated current CaC/secrets revisions and full check/repeat evidence remain unresolved. U2. |
| Git workflow | Main and versioning follow owner instructions. No feature branch is needed. Owner-directed direct main supersedes the PR recommendation. Mutable deployment references and lack of a final immutable accepted release remain recorded gaps. D8/U3. |
| Testing | Offline Python/JS, native PowerShell orchestration and real AAP runs provide different evidence. No custom role/container matrix is claimed. Full combined E2E and some convergence/check-mode evidence remain incomplete. U1/U2. |
| CI/CD and promotion | Pages CI runs browser checks. Equivalent automated Ansible/secret gates, release manifests and a tested full rollback/promotion procedure are not implemented. No enterprise dev/QA/prod process or CAB is invented for this demo. U3/U6. |
| Security | Vault/credential handling, platform transport validation, ownership safeguards and tested regional RBAC provide scoped evidence. The owner accepted the WinRM/WSUS lab exceptions and historical-username disposition (D10–D12). Secret rotation, image/SBOM coverage and complete access auditing remain unverified. U4/U5/U6. |

## Accepted low-impact deviations

Acceptance identifies either an agent disposition under the owner's
proportionality policy or an explicit owner decision, as stated in the row.
It does not mean full conformance. Effort estimates are qualitative; unresolved
material security decisions remain separate below.

| ID | Deviation, impact and benefit of correction | Cost, decision and revisit condition |
| --- | --- | --- |
| D1 | Keep playbooks/includes rather than package small project-specific stages into roles/collections. Packaging could help separate consumers. | A migration changes interfaces and test paths without a present consumer benefit. Retain now; revisit when multiple projects need a stable reusable unit. |
| D2 | Legacy filenames, mixed separators, numbered provisioning entry point and human-readable AAP names differ from strict CoP names. Uniform names would improve consistency. | Renaming affects JTs, links and existing consumers. Document the scheme and preserve contracts; revisit during an intentional breaking interface migration. |
| D3 | Explicit blank `vm_mac` extra var remains unsupported; extra vars outrank the derived fact. Could fail after VM creation. Current workflows provide explicit MACs; omit the field for automatic assignment. | Focused validation/derived-name correction is small but needs provisioning regression evidence. Retain the documented input boundary for this scope; revisit if a survey exposes blank MACs or automatic profiles become required. Do not claim this input is tested support. |
| D4 | Short rationale comments, visible operator summaries and immediate reset/reboot/cleanup ordering depart from blanket comment/verbosity/handler preferences. | Removing explanations or delaying required connection transitions harms operation. Retain specific purposeful cases; revisit a case if its dependency/order no longer exists. |
| D5 | Vault include_vars, scoped constants and AAP survey/workflow extra vars replace a pure structured inventory/defaults model. | Moving every value introduces CaC/interface churn. Keep explicit precedence and encrypted desired-state inputs; revisit conflicting public inputs or full inventory redesign. |
| D6 | Retain stdlib unittest and supporting Python without a complete Sphinx/type-hint migration; no authored production plugins. | Another runner and exhaustive annotation add dependencies/maintenance without demonstrating better deployment evidence. Existing behavioral tests remain useful. Revisit for a shared library/plugin interface or demonstrated type defects. |
| D7 | Keep unambiguous existing dot access, legitimate JSON serialization and established quoting where production lint accepts them. Independent verifier expectations intentionally duplicate the producer's contract. | Mechanical rewrites/custom filters create regression risk and can hide shared-oracle bugs. Revisit actual key collisions, confusing expressions or reusable transformations. |
| D8 | Work directly on main as the owner explicitly requested. | Branch/PR enforcement contradicts the current instruction. Retain exact commits and test records; revisit when the owner adopts a shared contribution workflow. |
| D9 | Retain the AD identity PowerShell batch although native user/group/OU modules exist. | Conversion must preserve ownership, safe retirement, administrator-added members and password policy behavior and needs live tests. Retain documented source choice; fresh runtime verification remains U1, not waived. Revisit when native reconciliation can demonstrate a simpler equivalent. |
| D10 | Existing lab inventory ignores WinRM server-certificate validation. The connection does not authenticate the server certificate. Trusted certificate deployment would strengthen endpoint identity. | Explicitly accepted by the owner on 2026-10-29 with documentation. Retain for this lab; revisit before production reuse or a change in network trust assumptions. No trust configuration was weakened by this review. |
| D11 | Existing WSUS content paths use HTTP rather than TLS. TLS would protect that transport. | Explicitly accepted by the owner on 2026-10-29 with documentation. Retain the lab design rather than adding a certificate/endpoint migration. Revisit before production reuse or changed network exposure. This exception is for WSUS HTTP, not a blanket waiver for other services. |
| D12 | Historical public documentation contains deployment usernames, removed from the current guides. History rewriting could remove those references. | The owner explicitly closed this concern on 2026-10-29. Do not rewrite history or change identities for this review. This decision concerns those usernames; passwords, tokens and other secrets remain protected under the policy. |

## Unresolved requirements and security decisions

| ID | Gap and practical implication | Required next evidence or decision |
| --- | --- | --- |
| U1 | No complete combined 29-stage pass; current 1.0.8 verifier fix only offline-tested. | The owner is responsible for the combined functional test. The agent must not launch it. Record the exact tested source and result when supplied; source-review checks remain separately accountable. |
| U2 | Full current CaC restore/check/repeat evidence absent; old core export is insufficient. | Reconcile current declarative objects and protected counterparts, recreate them on an authorized test AAP, then verify repeat application. |
| U3 | Mutable main/latest, incomplete promotion manifest, and Ansible CI parity. | Record actual source/image provenance per run; choose and verify an immutable accepted release and proportionate automated gates before claiming those CoP directives pass. Do not alter unrelated shared EEs. |
| U4 | WinRM certificate validation and WSUS HTTP are resolved as owner-accepted lab deviations D10/D11. No blanket exception for other service transports is inferred. | Record these exceptions without further WinRM/WSUS changes. Any additional transport concern needs its own evidence and disposition. No production-grade TLS or CIS compliance claim. |
| U5 | Dependency backend incomplete; Python crypt deprecation; full vendor EE image/SBOM and advisory applicability not established. | Account for APME's failure on synthetic collection records and the vendor warning against supported AAP. Obtain appropriate image/advisory evidence. Upstream pip-audit findings are leads, not proven Red Hat image vulnerabilities. |
| U6 | Historical usernames are closed by owner decision D12. Gitleaks does not establish arbitrary identifier privacy. Secret rotation cadence, full service-account access audit and rollback/promotion rehearsal are unverified. | Do not rewrite history for those usernames. Record the other evidence gaps separately; no unsupported assertion of secret exposure, rotation, complete audit or reliable whole-system rollback. |
| U7 | CIS benchmark, version/profile and individual Windows/DC controls not selected and assessed. | Select applicable benchmarks/controls before runtime assessment. Generic scanner checks and this review do not certify host compliance. No additional hardening imposed speculatively. |

## Conflicting guidance and chosen approaches

| Conflict | Chosen approach and reason |
| --- | --- |
| CoP hyphenated playbook naming vs coding-style snake_case | New YAML uses snake_case; preserve published legacy entry points. Avoid breaking AAP consumers for cosmetic uniformity. |
| CoP avoid-comments vs owner explain reason/goal/solution | Keep short linked rationale comments for non-obvious and foreign code. Routine actions remain in task names. |
| Historical EL7/Jinja restrictions vs actual supported EE | Use syntax supported by core 2.16.19 and its Jinja; do not emulate an unsupported old control node or upgrade the vendor runtime independently. |
| Native Ansible preference vs platform-specific API/format gaps | Use native state modules first; retain documented server-side WSUS, deterministic artifact, ownership and independent verification code. Native AD identity alternatives are acknowledged explicitly. |
| CoP role/dispatch/pytest guidance vs simplicity | Preserve coherent playbooks, native CaC modules and useful stdlib tests. Do not add a framework merely to resemble an example. Missing CaC restoration proof still remains a requirement. |
| PR/feature-branch process vs owner work-on-main instruction | Follow the owner; retain traceable commits and local verification. |
| Fast completion/proportionality vs final E2E evidence | Minor deviations may be accepted, but a failed/missing combined functional test is never renamed a successful review. |

## Tool results and limits

The latest APME snapshot targets the 1.0.8 source changes, scan
`f3e526da-ed14-48b8-9eeb-023c4c764117` on 2026-10-29. All six backend calls
returned; the dependency backend still failed internally. This scan does not
replace the outstanding functional test and restarted complete review.
APME source: pre-release `9c4372f79a8b537865040cea17cf9db7659614ad`.

| Backend | Observations | Disposition |
| --- | ---: | --- |
| Native | 785 | Style/complexity/structure observations triaged against source and supported scope; not 785 confirmed defects. |
| OPA | 58 | Policy observations require actual data/context and documented triage. |
| Ansible | 1 | Proposed equivalence between `ansible.platform.user` and OS `ansible.builtin.user` is inapplicable; these manage different objects. |
| Collection health | 11 | Findings in upstream integration/examples, not authored runtime content. Not an attestation of all upstream content. |
| Gitleaks | 0 | Pattern scan result only; separate Git history scan also found no pattern matches. |
| Dependency audit | 0 reported | **Incomplete:** pip-audit stopped on a synthetic collection record; seven such records exist in the session. Zero does not mean a clean audit. |

Total 855 observations. Suggested automatic edits were not blindly applied.
Supplemental pip-audit covered 25 real PyPI distributions in an isolated target
session; that session differs from the vendor EE. Vendor package versions and
backported fixes require separate applicability assessment.

APME installs bookkeeping distribution records for Ansible collections in its
isolated Python session, for example `ansible-collection-microsoft-iis`. Its
dependency backend then asks pip-audit to look these names up on PyPI. Collections
are distributed through Galaxy/private automation hub, so these synthetic names
are not actual PyPI packages. The audit stops at the first lookup failure. APME
logs that failure but returns an empty observation list, which cannot establish
a clean dependency scan. The supplemental audit excludes those seven synthetic
records and checks the 25 real Python distributions; collection compatibility,
provenance and content are assessed separately. This is an APME integration
limitation, not evidence that a collection or playbook is defective.

Offline regression and production-lint commands, results, live job references,
fix commits and optional recommendations are in the dated incomplete report.
The raw private evidence includes the scan JSON/stderr, collection provenance,
controller job records and preservation comparison. Keep this document sanitized.

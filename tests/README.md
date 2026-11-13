# Test code and its justification

## TLDR

These offline regressions check artifacts, access rules and failure paths using
synthetic inputs. They complement the normal AAP job-template and workflow tests.
They do not demonstrate real provisioning, Windows updates, application
installation, LDAP authentication or successful end-to-end operation.

Keep useful tests in the language of the behavior they exercise. Prefer Ansible
for deployment and integration orchestration. Converting every assertion or mock
to YAML would add complexity without improving the evidence.

## Python tests

Python is justified for directly exercising the Python assets, inspecting ZIP,
XML and multipart bytes, mocking API responses, and invoking Ansible's own
templating and execution engines. The standard-library `unittest` framework
avoids another test-runner dependency. PyYAML and Jinja2 come with the existing
Ansible tooling; profile-generation tests also need its existing `cryptography`
dependency. No additional test framework is required.

| Test files | Reason and evidence | Limit |
| --- | --- | --- |
| `test_offline_chocolatey_package.py`, `test_chocolatey_export.py` | Inspect actual package/export bytes, checksums, offline hooks, path rejection and deterministic rebuilds. | Do not contact Nexus or execute installers. |
| `test_nexus_path_validation.py`, `test_windows_patching_filters.py` | Exercise production assertions and filters through the Ansible conditional or templating engine, including malformed paths and update exclusions. | Do not validate Windows state or update availability. |
| `test_application_reboots.py`, `test_windows_activation_flow.py` | Run production Ansible conditions and block/always control flow with synthetic local inventories and mocked remote actions. Check reboot decisions, cleanup after failures, release only after activation/skip verification, and retained baseline inventory variables. | Do not execute real remote actions, asynchronous packaging, licensing, network changes or lifecycle publication. |
| `test_windows_activation_domain.py` | Exercise the actual topology parser against synthetic libvirt XML and injected read responses. | Does not inspect the hypervisor or prove real NIC cleanup. |
| `test_windows_teardown_scope.py`, `test_windows_reset.py` | Run the real baseline/target guards and cleanup readers against changed core evidence, foreign AD objects/grants, wrong clone identity, missing ownership, matching managed permissions and normal absent retries. | Does not delete VMs/API objects or replace the normal serialized reset acceptance. |
| `test_windows_runtime.py` | Exercise the selected-instance validator, exact network/clone ownership parsers, LDAP cleanup selection and actual Ansible certificate/preview guards. Reject wrong targets, ambiguous/shared authentication and foreign certificates. | Uses synthetic data; does not contact a hypervisor, remove authentication or replace serialized live acceptance and decommission. |
| `test_windows_guest_provenance.py` | Join observed Windows computer UUID/build/NIC data with both native domain definitions, owner markers, exact disks and bridges. Evaluate native Ansible full-run/login guards, selected HTTPS policy and truthful certificate-validation results. Refuse foreign integrations, wrong pins and extra NICs under either policy. | Synthetic identity/native data; no WinRM connection, TLS handshake, hypervisor mutation or isolation release occurs. |
| `test_windows_aap_management.py` | Exercise actual libvirt/NM operations with synthetic native responses, source-ownership rollback conditions, pre-hotplug primary preservation, foreign autoconnect and IPv4/IPv6 drift refusals, clone/cleanup winning orders and exact teardown XML. | Does not connect to AAP or a hypervisor, hotplug a NIC or replace serialized live acceptance. |
| `test_windows_connection_policy.py` | Run the actual encrypted loader with native Ansible: approved lab `ignore` works without a CA or inspection flag, `validate` refuses a missing CA and retains its public-CA file path. | Local synthetic inputs and public fixture certificate only; no guest connection or real TLS handshake occurs. |
| `test_active_directory_model.py` | Verify group expansion and the allowed access matrix; invoke the profile generator with fresh synthetic credentials. | Does not create AD accounts or test LDAP. |
| `test_active_directory_migration.py` | Inject an API fixture into the real ownership/migration inspector; reject foreign references and unsafe retirement. | Does not migrate live AAP objects. |
| `test_active_directory_verifier.py` | Run the complete 36-execution/360-permission matrix against a simulated API with at most one unfinished mock. Cover failed/forbidden launch cleanup, completed-ID reuse, shared API/sleep deadlines, cleanup reserve and late accepted launches. Exercise the actual urllib redirect handler and reject invalid platform roots before transport setup. All 21 checks pass locally and in the cached Core 2.20.10 image. | No real network request, certificate handshake or LDAP login is performed. |
| `test_active_directory_resources.py`, `test_active_directory_workflow.py`, `test_active_directory_update_policy.py` | Inspect production YAML, expand scoped grants, check graph ordering and evaluate the narrow update-title exclusion. | Structural checks; some depend on task names or layout and require maintenance during refactoring. |

The control-flow tests generate temporary mock action plugins under an ephemeral
collection namespace so Ansible can load them normally. This is test scaffolding,
not a vendored runtime collection. It is removed with the temporary directory,
is never deployed, and is not published to private automation hub.

Run from the repository root using the Python environment matching the actual
AAP execution environment. The review baseline is ansible-core **2.16.19**;
recheck the deployed EE before changing that baseline. Do not use APME's own
Python environment as the target runtime.

```bash
ANSIBLE_LOCAL_TEMP=/tmp/windows-review-ansible-local \
ANSIBLE_DEPRECATION_WARNINGS=true \
python3.12 -m unittest discover -s tests -v
```

The Python environment needs ansible-core, PyYAML, Jinja2 and `cryptography`,
plus `ansible-playbook` on PATH. The mocked control-flow tests create their own
temporary inventories; they need no live credentials or remote connections.
The two subprocess harnesses enable Ansible deprecation warnings and fail if
captured output contains an Ansible deprecation warning. This covers only the
paths exercised; the full static and live review must check all other paths.
Python dependency warnings must be assessed separately rather than suppressed.

Inspect the summary for failures **and skips**. Missing `ansible-playbook` can
skip the control-flow classes; a skipped class is missing coverage, not a pass.
Imports require the remaining dependencies and fail if they are absent.

## PowerShell tests

PowerShell is justified for exercising the actual PowerShell assets and their
Windows/.NET semantics while replacing WSUS, licensing, COM, CIM and registry
access with fixtures. Reimplementing those mocks in Python or YAML would test a
second implementation and add translation risk. These scripts use assertions
that throw on failure; no Pester installation is required.
The month-selection test also compiles a tiny C# enum fixture matching a WSUS
type, allowing the real relationship comparisons to run without installing WSUS.

| Test script | Behavior checked |
| --- | --- |
| `Test-WsusPatchMonthSelection.ps1` | Month validity, prerequisite/bundle closure and canonical selection; execute the actual external-sync agreement guard against pending, ordinary and already-accepted fixtures without accepting licenses. |
| `Test-WsusContentValidation.ps1` | Missing/truncated/corrupt payload accounting, transfer selection and avoiding repeated hashes. |
| `Test-WindowsUpdateClientPolicy.ps1` | Source-policy normalization and rejection of unsafe or unsupported client configuration. |
| `Test-ManagedUpdateSearch.ps1` | Managed-server search under restricted COM access, exact observed-title matching, reboot markers and incomplete-search rejection. |
| `Test-WindowsEvaluationActivation.ps1` | Evaluation-only licensing, check mode, network-topology guards and activation failures using mocks. |
| `Test-WindowsDemoProof.ps1` | Build comparison and trustworthy package-history sequencing, including missing, failed and reversed evidence. |

Run each script in a separate Windows PowerShell process from a checkout on the
Windows test host. Separate processes prevent one script's mocked commands from
leaking into another. These commands do not require an execution-policy bypass.
The proof test expects the result container normally provided by
`ansible.windows.win_powershell`:

```powershell
powershell.exe -NoProfile -File tests/Test-WsusPatchMonthSelection.ps1
powershell.exe -NoProfile -File tests/Test-WsusContentValidation.ps1
powershell.exe -NoProfile -File tests/Test-WindowsUpdateClientPolicy.ps1
powershell.exe -NoProfile -File tests/Test-ManagedUpdateSearch.ps1
powershell.exe -NoProfile -File tests/Test-WindowsEvaluationActivation.ps1
powershell.exe -NoProfile -Command '$Ansible = @{ Changed = $false; Result = @{} }; & ./tests/Test-WindowsDemoProof.ps1 -ReporterPath ./assets/show-windows-demo-proof.ps1'
```

Check each exit code and assertion result. These are mocked regressions; real
Windows PowerShell and live service integration still need AAP validation.

For AAP execution, `verify_windows_regressions.yml` stages this repository's
`assets/` and `tests/` directories in a temporary workspace on each of the two
managed servers, runs the five standalone scripts in separate Windows PowerShell
processes, and runs the proof rules through `win_powershell` with its real Ansible
result container. It checks every exit/result and removes the staged sources in
an `always` block. It uses the normal Windows inventory, Machine credential and
supported EE; no packages, execution-policy changes or additional Python helper
are required. Check mode is refused because it cannot establish executed tests.
Output is protected by default. For a failed diagnostic rerun, select `true` in
the template's diagnostic-output survey. API launches must send the string
`"true"` for `windows_regression_diagnostics`; this is a multiple-choice survey,
not a JSON boolean field. The override exposes mock errors and temporary paths
to job readers and does not expose deployment credentials.

## JavaScript walkthrough tests

The three JavaScript test files under `demo/tests/` and `demo-with-aap/tests/`
exercise the actual browser walkthrough's state and orchestration models using
Node's built-in runner. They check ordering, cancellation, source links and
static assets. JavaScript is justified because these are JavaScript presentation
components; Ansible does not execute their state transitions.

```bash
node --test demo/tests/scenario.test.cjs
node --test demo-with-aap/tests/scenario.test.cjs demo-with-aap/tests/orchestration.test.cjs
```

These tests run in the existing GitHub Pages publication workflow. They do not
launch AAP jobs, prove the depicted deployment, or exercise a real browser.
The current publication workflow does not run the Python or PowerShell suites;
those results must be recorded separately until dedicated CI is added.

## Review evidence

The 1.0.2 review patch passed all 103 Python tests on Python 3.12 with
ansible-core 2.16.19 and all 14 JavaScript tests, with no skipped tests.
The Python run reported the existing ansible-core dependency's `crypt`
deprecation warning; it was retained for assessment rather than suppressed.
This patch does not claim a new PowerShell-on-Windows execution result.

The 1.0.8 transport regressions failed against the old implementation and passed
after the focused client correction. They cover HTTP 301, 302, 303, 307 and 308
for same-origin and cross-origin destinations, and six invalid target-root
forms. They add two test methods, without another framework or live connection.
The dated review record contains the complete current suite results.

Record the tested commit, interpreter/core versions, executed suites, failures,
skips and unexecuted suites in the review evidence. Review these scripts for
readability, useful assertions, fixture isolation and honest scope alongside the
production code. The final dated review report must separately confirm live
functionality and the complete scoped AAP end-to-end result.

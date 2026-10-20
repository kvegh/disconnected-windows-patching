# Monthly Windows patch ceilings

Use **Disconnected Windows Patching - Set WSUS Patch Ceiling** to prepare and
publish a monthly OS/.NET baseline on internal WSUS. This changes available
content; it does not install updates on endnodes.

The required dropdown contains January 2026 through September 2026, the regular
monthly OS cumulative releases present for both supported Windows versions when
the feature was implemented. The default is April 2026. Display names map to
canonical release months internally. The playbook rejects unsupported choices.
Update the audited choices and survey together when more releases are available.

## What the selection means

Selecting April 2026 chooses each OS's regular April cumulative update, the
newest applicable .NET cumulative release at or before April, and required
prerequisites. .NET does not have a release every month. Older superseded
prerequisites remain eligible when necessary.

The ceiling uses release months in Microsoft update titles, with explicit
audited mappings required for prerequisite titles without a release month.
It does not confuse metadata revision dates or local arrival dates with the
original release month. Unknown or later prerequisites, expired selections and
ambiguous shared bundles stop the job before policy changes.

The internal policy approves the selected cumulative releases and prerequisites
for All Computers, and declines other catalogue entries server-wide. This also
hides unused older cumulative updates: the selected cumulative baseline includes
their fixes without offering every historical package. Preview updates and
other architectures are excluded. Automatic approval rules, automatic approval
refresh and scheduled internal synchronization are disabled.

The job cannot uninstall updates from a machine already newer than the ceiling.
Existing downloaded client content and installed state require separate
assessment; changing availability is not a rollback procedure.

## Ansible stages

1. Validate the named month, inventory roles, catalogue identities and internal
   file readiness without changing policy.
2. On external WSUS, approve the explicit historical baseline for an empty
   download-only group. Reuse existing files and budget only missing verified
   payloads against the configured disk reserve. This does not target clients.
3. Wait for WSUS downloads and verify their content hashes. A required license
   agreement causes failure; the job never accepts license terms automatically.
4. Reuse the existing export and internal HTTP pull/import playbooks, including
   their manifest and SHA-256 verification.
5. Apply internal approvals/declines, re-read the resulting policy, and save the
   verified month. AAP artifacts contain the selected update identities and
   verification result. Detailed diagnostics remain protected by default.

Ansible handles orchestration, services, files, transfer, waiting and artifacts.
The WSUS management operations use its native PowerShell API through
`ansible.windows.win_powershell`.

The saved internal policy is reapplied after subsequent runs of
`replicate_and_import.yml`. WSUS has no native persistent month-filter setting:
this is reconciliation after import, not an atomic visibility boundary during
an import. Direct manual approval changes or synchronization outside these
playbooks can cause drift; validate or reapply the ceiling before client patching.
Changing from one month to another never deletes downloaded update files.

## Run and preview

Use the Job Template survey, or an existing protected inventory and credentials:

```bash
ansible-playbook -i YOUR_PROTECTED_INVENTORY set_internal_wsus_patch_month.yml \
  -e '{"wsus_patch_month":"April 2026"}'
```

Select AAP job type **Check**, or add `--check` locally, for a read-only plan.
Check mode reports selected identities and missing internal payloads without
downloading, exporting, importing or changing approvals. Normal mode prepares
content before applying policy. Catalogue presence alone does not mean the
corresponding update files are ready.

## Reproduce the Job Template configuration

`configure_wsus_patch_ceiling_template.yml` refreshes the project and configures
the template, credential associations and survey using
`ansible.controller.job_template`. Its separate optional controller administration
dependency is pinned in `configuration/collections/requirements.yml`; it is not
added to the Windows execution environment's runtime requirements.

Supply the following through protected configuration: `wsus_controller_host`,
`wsus_controller_token`, `wsus_controller_inventory`, `wsus_controller_project`,
`wsus_controller_execution_environment` and `wsus_controller_credentials`.
The credentials must include the existing Windows Machine and Vault credentials.
TLS certificate verification remains enabled. Existing standard controller
authentication environment variables can also supply the connection.

```bash
ansible-playbook configure_wsus_patch_ceiling_template.yml \
  -e @YOUR_PROTECTED_CONTROLLER_CONFIGURATION
```

## References and verification

- [Microsoft: approvals, declines and update visibility](https://learn.microsoft.com/en-us/windows-server/administration/windows-server-update-services/manage/updates-operations)
- [Microsoft: cumulative and servicing-stack updates](https://learn.microsoft.com/en-us/windows/deployment/update/servicing-stack-updates)
- [Microsoft: checkpoint cumulative updates](https://learn.microsoft.com/en-us/windows/deployment/update/catalog-checkpoint-cumulative-updates)
- [Existing WSUS transfer pipeline](wsus-data-flow.md)
- [Installed build assessment](../assess_windows_patch_level.yml)

`tests/Test-WsusPatchMonthSelection.ps1` exercises invalid/missing months,
architecture and preview filtering, .NET fallback, prerequisites, explicit
prerequisite mappings and shared-bundle conflicts. Run it with an existing
Windows PowerShell 5.1 or PowerShell 7 installation; it needs no WSUS service.

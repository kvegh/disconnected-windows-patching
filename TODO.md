# Demo TODO

## Review Ansible use and external dependencies

- Review every automation stage to identify whether it uses native Ansible
  modules only. List each exception: PowerShell scripts, Windows/WSUS APIs,
  command-line utilities, custom helpers and direct external API calls.
- For each exception, record its purpose, how Ansible invokes it, why a native
  module is insufficient, and whether it can be replaced with supported Ansible
  content. Include controller configuration, content transfer and client patching.
- Document the resulting module/dependency map and remaining replacements.

## Permanent IP and MAC assignments

- Define permanent addresses for every demo VM and every relevant NIC, including
  the AAP management and isolated interfaces, test server, monitoring server,
  remote management host, external WSUS/Nexus, internal WSUS/Nexus on both networks,
  and all managed Windows endnodes.
- Assign and preserve explicit unique MAC addresses in VM deployment so deleting
  and recreating a VM does not change its NIC identities.
- Prefer MAC-bound DHCP reservations where we control DHCP. On the management
  LAN, coordinate reservations with its actual DHCP server; libvirt reservations
  only apply to networks where libvirt provides DHCP. Use guest static addresses
  outside DHCP pools where reservations are unavailable.
- Verify address/MAC uniqueness, exclude static addresses from dynamic pools, and
  ensure persistent reservations survive network restarts and host reboots.
- Identify and rename Windows adapters by MAC as Management or Isolated; do not
  rely on enumeration order. Keep isolated NICs without a gateway or DNS server.
- Keep AAP inventory connection addresses aligned with the permanent assignments.
  Verify WinRM from the actual AAP execution environment and confirm isolated
  clients cannot obtain Internet access through dual-connected hosts.
- Store the complete address/MAC mapping in AAP inventory or Vault-encrypted
  configuration, including deployment/workflow inputs and DHCP configuration.
  Keep actual hostnames, IPs, MAC assignments, and credentials out of plaintext Git.
- Fixed MAC deployment inputs are implemented. Automate DHCP reservations to
  match those inputs; libvirt generates MACs when explicit inputs are omitted.

## WSUS population follow-up

- Run and validate the new sync, export and import stages with current Microsoft updates.
- Validate applicability and prerequisite/checkpoint coverage on both older base images.
- Internal monthly approval/visibility ceilings are implemented in
  `set_internal_wsus_patch_month.yml`, with saved-policy reapplication after imports.
  Client patch installation is a separate stage.
- Installed-state assessment is implemented in `assess_windows_patch_level.yml`.
  Add client applicability scans as a separate read-only stage.
- Reproducible named-month selection, historical content download and internal
  approval are implemented. Keep newer releases available externally for the
  next demonstration stage and add survey choices after auditing new catalogues.
- Validate the pinned Nexus/Chocolatey downloads and vaulted inputs in live service setup.
- Validate Task Scheduler network configuration on all four freshly cloned VMs.
- Exercise the five application stages: sync, export, import, baseline deployment and upgrade.
- Add metadata snapshot/import-log retention without deleting active transfer files.
- Migrate pinned community IIS modules to microsoft.iis before their upstream removal.

## Active Directory and AAP permissions from nested groups

- Stand up a domain controller for the demo. Decide between a Samba AD DC
  container (fastest, real AD schema) and a Windows Server evaluation VM (most
  credible in front of a customer). Promoting the external WSUS host is viable
  for a throwaway environment: the local SAM is not destroyed, it is retained
  solely for Directory Services Restore Mode, but normal-mode local logon stops
  resolving, so inventory any service running under a machine-local identity
  first. Microsoft discourages WSUS on a domain controller mainly because of the
  Windows Internal Database, not the SAM.
- Build a nested test group structure following AGDLP, with users in global role
  groups that are themselves members of domain-local resource groups, so the
  demo exercises indirect membership rather than only direct membership.
- Decide which AAP instance carries this work. The nginx vhost and certificate
  for a second instance already exist in hactarconfig but nothing is serving it,
  and LDAP authenticator plus map ordering should not be rehearsed on the
  instance the monitoring self-healing demo depends on.
- Configure the LDAP authenticator against the domain controller using
  NestedActiveDirectoryGroupType, a read-only bind account and the group search
  base. Place the issuing CA in the platform trust store for LDAPS; that trust
  configuration is not carried across platform upgrades.
- Define the authenticator maps as code through the gateway_authenticator_maps
  role rather than the web interface. Group values are full group distinguished
  names under triggers.groups, with has_or for any-of and has_and for all-of.
  Set order explicitly so map precedence is version controlled.
- Verify that a user whose membership is only indirect still lands in the mapped
  team, and read the evaluation results back from the user endpoint rather than
  inferring success from the login succeeding.
- Verify revocation: remove a user from the group, log in again, and confirm the
  team membership and role are withdrawn when revoke is set.
- Compare nested group resolution against the Active Directory matching rule in
  chain for login latency on a directory of realistic size, and record which one
  the demo uses and why.
- Raise documentation feedback that the lowercase group identifier requirement
  in the platform security guide is stale, since case-insensitive map matching
  became the default and its feature flag was removed.

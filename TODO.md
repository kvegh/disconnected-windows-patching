# Demo TODO

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

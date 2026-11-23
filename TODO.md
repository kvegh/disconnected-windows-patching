# TODO

- **AAP execution node inside the isolated network** instead of the second
  NIC of the AAP VM (documented shortcut 1). A separate execution node VM in
  the isolated network, joined to the AAP mesh, so the AAP VM is not bridged
  into the disconnected network. Costs: one more VM (hypervisor memory), mesh
  configuration, an instance group for the internal job templates. Tracked as
  bead-wd-0gnz.45.2.
- **First deploy checks** (not verifiable without targets; see
  `design_decisions_history.md`, 2026-11-23): Nexus 3.98.3-01 Windows layout
  (`bin\install-nexus-service.bat`), Nexus search/asset download of NuGet
  packages by `name`/`version`, IIS anonymous reads of `/export` on the WSUS
  site, WsusUtil import of the `.xml.gz` export, NVRAM file path of the UEFI VM,
  repo server disk space for the patch month (free-disk check in stage 3).
- **Active Directory extension**: moved to `kvegh/AAP-ActiveDirectory`
  (2026-11-23); the old AD code stays in `archive/` as reference.

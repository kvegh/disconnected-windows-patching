/* Public, illustrative data only. This walkthrough does not call AAP. */
(() => {
  'use strict';
  const steps = [
    {
      title: 'Deploy the servers',
      description: 'Create two repository servers and two managed Windows servers. The first pieces of the datacenter arrive.',
      short: 'Four Windows servers, ready for configuration.',
      source: '01-win-vm-setup.yml',
      example: '- name: Create an independent Windows disk\n  ansible.builtin.command:\n    argv:\n      - qemu-img\n      - convert\n      - -O\n      - qcow2\n      - "{{ base_image }}"\n      - "{{ clone_disk }}"\n    creates: "{{ clone_disk }}"\n\n# The VM is then created with virt-install.',
      flow: 'Four servers. Two distinct network roles.'
    },
    {
      title: 'Configure Windows',
      description: 'Set up guest networking and management access. Verify evaluation licensing and restore the intended NIC topology after any activation.',
      short: 'Networking, management access and licensing.',
      source: 'configure_windows_server_basics.yml',
      example: '- name: Configure the Windows hostname\n  ansible.windows.win_hostname:\n    name: "{{ desired_name }}"\n  register: hostname_result\n\n- name: Complete the required restart\n  ansible.windows.win_reboot:\n  when: hostname_result.reboot_required',
      flow: 'The internal repository has a separate management connection.'
    },
    {
      title: 'Prepare the repositories',
      description: 'Prepare Windows features and required reboots, then configure WSUS and Nexus. The internal clients use their internal update and application sources.',
      short: 'WSUS for Windows. Nexus for applications.',
      source: 'setup_wsus.yml',
      example: '- name: Install Windows Update Services\n  ansible.windows.win_feature:\n    name:\n      - UpdateServices\n      - UpdateServices-WidDB\n      - UpdateServices-Services\n    state: present\n    include_management_tools: true',
      flow: 'Repository services are ready; content comes next.'
    },
    {
      title: 'Download selected content',
      description: 'External WSUS synchronizes with Microsoft and downloads the selected OS and .NET files. The application branch acquires pinned 7-Zip and Git installers.',
      short: 'Selected content arrives on the connected side.',
      source: 'sync_external_wsus.yml',
      example: '- name: Synchronize selected Microsoft updates\n  ansible.windows.win_powershell:\n    script: |\n      $wsus = Get-WsusServer\n      $subscription = $wsus.GetSubscription()\n      $subscription.StartSynchronization()\n      # Then wait, select and verify files.',
      flow: 'Microsoft → external WSUS. Motion illustrates the download path.'
    },
    {
      title: 'Export and publish through IIS',
      description: 'Export compressed WSUS metadata and publish its manifest and existing update files through a management-only IIS site. The application export is a separate ZIP served by Nexus.',
      short: 'Compressed metadata and update files become available.',
      source: 'export_external_wsus.yml',
      example: '- name: Export compressed WSUS metadata\n  ansible.windows.win_command:\n    cmd: >-\n      WSUSutil.exe export\n      "{{ metadata_gzip }}" "{{ export_log }}"\n\n- name: Publish the static export\n  community.windows.win_iis_website:\n    name: WSUS Export\n    physical_path: "{{ export_root }}"\n    state: started',
      flow: 'IIS publishes .xml.gz metadata, a manifest and separate update files.'
    },
    {
      title: 'Pull and import internally',
      description: 'The internal repository initiates the connection and pulls the published export: WSUS metadata and update files from external IIS, and application packages from external Nexus. It verifies checksums before importing locally.',
      short: 'Internal requests the export. External returns the data.',
      source: 'replicate_and_import.yml',
      example: '- name: Pull an export from the internal side\n  hosts: internal_repository\n  gather_facts: false\n  tasks:\n    - name: Request and verify the external export\n      ansible.windows.win_get_url:\n        url: "{{ external_export_url }}"\n        dest: "{{ internal_file }}"\n        checksum: "{{ trusted_sha256 }}"\n        checksum_algorithm: sha256\n        use_proxy: false\n        follow_redirects: none',
      flow: 'PULL: internal requests → external serves → data returns internally.'
    },
    {
      title: 'Publish the patch baseline',
      description: 'Apply the named April 2026 WSUS ceiling. Both content imports must be complete before clients receive this controlled baseline.',
      short: 'A named monthly baseline controls what clients receive.',
      source: 'set_internal_wsus_patch_month.yml',
      example: '- name: Apply a named WSUS baseline\n  ansible.builtin.include_tasks:\n    file: tasks/apply_wsus_patch_month.yml\n  vars:\n    wsus_patch_month: "{{ selected_month }}"\n\n# Approvals and content readiness are\n# verified before client patching.',
      flow: 'Internal policy selects the April 2026 baseline.'
    },
    {
      title: 'Patch the Windows servers',
      description: 'Each managed server installs the internal WSUS baseline, completes required reboot cycles and rescans. The two hosts can run in separate jobs.',
      short: 'OS and .NET updates come from internal WSUS.',
      source: 'update_managed_windows.yml',
      example: '- name: Install updates from managed WSUS\n  ansible.windows.win_updates:\n    server_selection: managed_server\n    category_names:\n      - SecurityUpdates\n      - CriticalUpdates\n      - UpdateRollups\n    state: installed\n    reboot: true',
      flow: 'Internal WSUS → Windows Server 2022 and 2025.'
    },
    {
      title: 'Install baseline applications',
      description: 'Install the older pinned 7-Zip and Git packages from the internal Nexus baseline feed. The public Chocolatey source remains disabled.',
      short: 'Known application versions establish the starting point.',
      source: 'deploy_baseline_applications.yml',
      example: '- name: Install a pinned baseline package\n  chocolatey.chocolatey.win_chocolatey:\n    name: "{{ package_id }}"\n    version: "{{ baseline_version }}"\n    source: "{{ internal_baseline_feed }}"\n    state: present',
      flow: 'Internal Nexus → baseline 7-Zip and Git installations.'
    },
    {
      title: 'Upgrade the applications',
      description: 'Switch to the internal current feed and upgrade to the newer pinned releases. The version numbers change on both managed servers.',
      short: '7-Zip 26.03 → 26.04. Git 2.55 → 2.56.',
      source: 'upgrade_applications.yml',
      example: '- name: Upgrade to a pinned current package\n  chocolatey.chocolatey.win_chocolatey:\n    name: "{{ package_id }}"\n    version: "{{ current_version }}"\n    source: "{{ internal_current_feed }}"\n    state: latest',
      flow: 'The application versions update; the source stays internal.'
    },
    {
      title: 'Verify the final state',
      description: 'Inspect OS builds, exact application versions and configured sources. Completion also requires that the Windows reboot markers are clear.',
      short: 'Expected versions. Internal sources. Reboots complete.',
      source: 'assess_windows_patch_level.yml',
      example: '- name: Inspect installed Windows updates\n  ansible.windows.win_powershell:\n    script: |\n      $Ansible.Changed = $false\n      Get-HotFix | Select-Object HotFixID\n\n# The actual jobs also inspect build,\n# source policy and reboot markers.',
      flow: 'The complete illustrated environment, ready to explore.'
    }
  ].map((step, index) => Object.freeze({ ...step, number: index + 1 }));

  function stateAt(stage) {
    const index = Math.max(0, Math.min(steps.length, Number.isFinite(stage) ? Math.trunc(stage) : 0));
    return Object.freeze({
      stage: index,
      history: steps.slice(0, index),
      current: steps[index - 1] || null,
      next: steps[index] || null,
      servers: index >= 1,
      configured: index >= 2,
      services: index >= 3,
      acquired: index >= 4,
      exported: index >= 5,
      imported: index >= 6,
      baseline: index >= 7,
      patched: index >= 8,
      applications: index >= 9 ? (index >= 10 ? 'current' : 'baseline') : 'none',
      verified: index >= 11,
      versions: index >= 9 ? (index >= 10 ? { zip: '26.04', git: '2.56', gitFull: '2.56.0.windows.2' } : { zip: '26.03', git: '2.55', gitFull: '2.55.0.windows.5' }) : null
    });
  }

  function sourceUrl(path, pageUrl) {
    if (!steps.some(step => step.source === path)) throw new Error('Unknown source file');
    const url = new URL(pageUrl);
    const suffix = '.github.io';
    const owner = url.hostname.endsWith(suffix) ? url.hostname.slice(0, -suffix.length) : null;
    const repository = url.pathname.split('/').filter(Boolean)[0];
    if (owner && repository) return `https://github.com/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}/blob/main/${path}`;
    // The deployment derives its public repository from its Pages URL. Local
    // previews may provide the same URL using ?site=https://OWNER.github.io/REPO/.
    const publicSite = url.searchParams.get('site');
    if (publicSite) {
      try {
        const preview = new URL(publicSite);
        if (preview.hostname.endsWith(suffix) && preview.pathname.split('/').filter(Boolean).length) return sourceUrl(path, preview.href);
      } catch { /* Invalid optional preview URLs leave source links unavailable. */ }
    }
    return null;
  }

  const api = Object.freeze({ steps: Object.freeze(steps), stateAt, sourceUrl });
  globalThis.WindowsDemo = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})();

/* Browser UI requires JavaScript: the walkthrough is an interactive static page. */
/* Public, illustrative data only. This walkthrough does not call AAP. */
(() => {
  'use strict';
  const scopes = ['both', 'both', 'both', 'connected', 'connected', 'internal', 'internal', 'internal', 'internal', 'internal', 'internal'];
  const targets = ['deployment', 'all', 'repositories', 'external', 'external', 'repository', 'repository', 'clients', 'clients', 'clients', 'clients'];
  const steps = [
    {
      title: 'Deploy the servers',
      description: 'The infra playbook creates the isolated network, gives AAP a NIC in it and starts the external repository, the internal repository and the Windows Server 2022 and 2025 VMs in parallel. Snapshot stage-1-OS-install.',
      short: 'One infra run: network, AAP NIC, four VMs.',
      source: 'playbooks/aap-infra.yml',
      example: '- name: Create and start the Windows VMs\n  ansible.builtin.command:\n    argv: "{{ virt_install_argv + nic_argv + boot_argv }}"\n  loop: "{{ windows_vms }}"\n  when: item.name not in defined_vms.stdout_lines',
      flow: 'Fixed addresses come from libvirt DHCP host entries.'
    },
    {
      title: 'Configure and activate Windows',
      description: 'Set host names and the Windows Update policy, then activate the evaluation licenses once through a temporary NIC that is detached again.',
      short: 'Host names, update policy, evaluation activation.',
      source: 'playbooks/windows-basics.yml',
      example: '- name: Set the host name\n  ansible.windows.win_hostname:\n    name: "{{ inventory_hostname }}"\n\n- name: Set the Windows Update policy\n  ansible.windows.win_regedit:\n    path: "{{ item.path }}"\n    name: "{{ item.name }}"\n    data: "{{ item.data }}"',
      flow: 'Managed servers know only the internal WSUS.'
    },
    {
      title: 'Prepare the repositories',
      description: 'One sequential setup: features and the Chocolatey CLI with a single reboot, then WSUS and Nexus on both repository servers and the internal feed as the only Chocolatey source. Snapshot stage-2-basics-repos.',
      short: 'WSUS for Windows. Nexus Chocolatey feed for applications.',
      source: 'playbooks/repositories-setup.yml',
      example: '- name: Install WSUS and IIS static content\n  ansible.windows.win_feature:\n    name:\n      - UpdateServices-Services\n      - UpdateServices-WidDB\n      - Web-Static-Content\n    include_management_tools: true',
      flow: 'Repository services are ready; content comes next.'
    },
    {
      title: 'Download selected content',
      description: 'External WSUS synchronizes with Microsoft and downloads only the configured patch month. AAP downloads the pinned public Chocolatey community packages and uploads them to the external feed.',
      short: 'One patch month and pinned packages arrive on the connected side.',
      source: 'playbooks/wsus-external-fill.yml',
      example: '- name: Approve and download the patch month\n  ansible.builtin.include_tasks: tasks/wsus-month-approve.yml\n  vars:\n    wsus_ready_retries: "{{ wsus_download_retries }}"',
      flow: 'Microsoft updates + community packages → external repository.'
    },
    {
      title: 'Export and publish through IIS',
      description: 'Export the WSUS metadata and pack the pinned packages into one archive; the WSUS web site publishes both next to the update files. Snapshot stage-3-external-repo-fill.',
      short: 'Metadata, update files and the package archive become available.',
      source: 'playbooks/applications-external-fill.yml',
      example: '- name: Pack the export archive\n  community.windows.win_zip:\n    src: "{{ fill_package_dir }}\\\\*"\n    dest: "{{ repository_export_dir }}\\\\applications.zip"',
      flow: 'IIS publishes .xml.gz metadata, update files and applications.zip.'
    },
    {
      title: 'Pull and import internally',
      description: 'The internal repository pulls the export over HTTP, checks every file against its checksum and imports WSUS metadata and packages into its own WSUS and Nexus feed. Snapshot stage-4-internal-repo-import.',
      short: 'Internal requests the export. External returns the data.',
      source: 'playbooks/wsus-internal-import.yml',
      example: '- name: Download the update files\n  ansible.windows.win_get_url:\n    url: "{{ import_repo_ext_url }}/Content/{{ item.0 }}"\n    dest: "{{ import_content_dir }}\\\\{{ item.0 | replace(\'/\', \'\\\\\') }}"\n    checksum: "{{ item.1.checksum }}"\n    checksum_algorithm: sha1',
      flow: 'PULL: internal requests → external serves → data returns internally.'
    },
    {
      title: 'Set the patch level',
      description: 'Approve only the configured patch month on the internal WSUS; nothing newer is offered. The proof report records the starting level. Snapshot stage-5-patch-level-cutoff-set.',
      short: 'One approved month controls what clients receive.',
      source: 'playbooks/patch-level-cutoff.yml',
      example: '- name: Approve the patch month\n  ansible.builtin.include_tasks: tasks/wsus-month-approve.yml\n  vars:\n    wsus_ready_retries: "{{ wsus_import_ready_retries }}"',
      flow: 'Internal policy selects the configured month.'
    },
    {
      title: 'Patch the Windows servers',
      description: 'Both managed servers install the approved updates from the internal WSUS in parallel, with all required reboots. Proof report, snapshot stage-6-OS-patched.',
      short: 'OS and .NET updates come from internal WSUS.',
      source: 'playbooks/windows-patch.yml',
      example: '- name: Install the approved updates\n  ansible.windows.win_updates:\n    server_selection: managed_server\n    category_names: \'*\'\n    reboot: true',
      flow: 'Internal WSUS → Windows Server 2022 and 2025.'
    },
    {
      title: 'Install baseline applications',
      description: 'Install the older pinned 7-Zip and Git community packages from the internal feed. The public Chocolatey source is removed. Proof report, snapshot stage-7-apps-baseline.',
      short: 'Known application versions establish the starting point.',
      source: 'playbooks/applications-deploy.yml',
      example: '- name: Install the pinned application versions of the track\n  chocolatey.chocolatey.win_chocolatey:\n    name: "{{ item.id }}"\n    version: "{{ item.version }}"\n    source: "{{ chocolatey_source_name }}"',
      flow: 'Internal Chocolatey feed → baseline 7-Zip and Git installations.'
    },
    {
      title: 'Upgrade the applications',
      description: 'Upgrade to the newer pinned versions from the same internal feed. Proof report, snapshot stage-8-apps-upgraded.',
      short: '7-Zip 26.03 → 26.04. Git 2.55 → 2.56.',
      source: 'playbooks/applications-deploy.yml',
      example: '- name: Install the pinned application versions of the track\n  chocolatey.chocolatey.win_chocolatey:\n    name: "{{ item.id }}"\n    version: "{{ item.version }}"\n    state: upgrade',
      flow: 'The application versions update; the source stays internal.'
    },
    {
      title: 'Show the proof report',
      description: 'The proof report appends one CSV line per stage (OS build, newest update, application versions) on each managed server and prints the history; a desktop shortcut shows it in colour.',
      short: 'One line per stage: build, newest update, versions.',
      source: 'playbooks/proof-report.yml',
      example: '- name: Append the line of this stage\n  community.windows.win_lineinfile:\n    path: "{{ proof_file }}"\n    line: "{{ proof_line }}"\n    insertafter: EOF',
      flow: 'The complete illustrated environment, ready to explore.'
    }
  ].map((step, index) => Object.freeze({ ...step, number: index + 1, scope: scopes[index], target: targets[index] }));

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

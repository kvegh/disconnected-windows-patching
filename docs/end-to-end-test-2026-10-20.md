# Fresh Windows end-to-end test — 2026-10-20

Status: **21-stage workflow passed; follow-up reboot verification in progress**.
Workflow 2303 completed all 21 stages in **3h48m50s**.
Started 2026-10-20 at 21:13:04 UTC; finished 2026-10-21 at 01:01:54 UTC.

## Scope and required results

Rebuild only the external repository server, internal repository server, Server
2022 endnode and Server 2025 endnode, including replacement of their owned clone
disks. Preserve all other VM definitions/states and the original Windows images.
Both managed guests must have 4096 MiB RAM allocated.

The sequence is deployment, Windows basics, per-clone evaluation activation,
repository preparation, WSUS/Nexus/Chocolatey setup, external synchronization and
file downloads, export, internal pull/import, internal April 2026 WSUS ceiling,
independent endnode patch/reboot jobs, baseline applications, then upgraded
applications. Both imports converge before the ceiling; both patch jobs converge
before baseline applications. External WSUS retains its synchronized catalogue.

Final OS evidence must show Server 2022 build `20348.5020` and Server 2025 build
`26100.32690`, applicable April .NET updates, verified internal WSUS source, no
remaining approved updates and no pending reboot. Application evidence must show
7-Zip `26.3.0` and Git `2.55.0.5` before upgrades to `26.4.0` and `2.56.0.2`,
using only the selected internal feed.

## Teardown and preservation evidence

| Operation | Job | Result | Execution time |
|---|---|---|---|
| Capture VM/image preservation baseline | 2288 | Passed; 11 domains and two base images captured | 19.2s |
| External repository clone and owned disk removal | 2291 | Passed | 118.0s |
| Internal repository clone and owned disk removal | 2297 | Passed | 13.0s |
| Server 2022 clone and owned disk removal | 2299 | Passed | 9.2s |
| Server 2025 clone and owned disk removal | 2300 | Passed | 10.3s |
| Independent preservation and disk-absence verification | 2301 | Passed; seven unrelated definitions/states and both images unchanged | 13.8s |

The first teardown exposed default whole-disk hashing in an otherwise metadata-only
file inspection. Implementation `07e1200` disables checksum/MIME reads while
preserving all deletion authorization guards. Queued jobs 2293, 2294 and 2295
were canceled before deletion and replaced by the successful targeted jobs above.
The same implementation extends the existing workflow to the requested sequence.
Native controller read-back checks and an unchanged second configuration passed;
production lint passed for all three changed Ansible files.

## Fresh workflow execution

Workflow 2303 uses the existing deployment workflow, the internal April 2026
selection and explicit managed/repository memory values of 4096/8192 MiB.
Four creation jobs started in parallel. Detailed environment-specific evidence
and credentials remain in protected AAP artifacts and local diagnostic storage.

## Verified stage results

| Stage | Job | Result | Execution time |
|---|---|---|---|
| Create external repository VM | 2304 | Passed | 22m21s |
| Create internal repository VM | 2305 | Passed | 22m22s |
| Create Server 2022 endnode | 2306 | Passed | 22m12s |
| Create Server 2025 endnode | 2307 | Passed | 22m27s |
| Configure Windows basics | 2309 | Passed | 7m35s |
| Verify/activate evaluations | 2311 | Passed | 3m32s |
| Prepare features, installers and reboots | 2313 | Passed | 4m3s |
| Set up WSUS and client policies | 2315 | Passed | 5m32s |
| Set up Nexus/Chocolatey | 2316 | Passed | 8m45s |
| Check WSUS prerequisites | 2318 | Passed | 3m55s |
| Populate external Chocolatey | 2320 | Passed | 50s |
| Export/publish Chocolatey | 2324 | Passed | 56s |
| Internal Chocolatey pull/import | 2325 | Passed | 2m18s |
| Synchronize/download external WSUS | 2322 | Passed | 49m10s |
| Export/publish WSUS | 2327 | Passed | 2m41s |
| Internal WSUS pull/import | 2329 | Passed | 31m43s |
| Enforce internal April 2026 ceiling | 2331 | Passed | 21m10s |
| Patch Server 2022 | 2333 | Passed | 41m28s |
| Patch Server 2025 | 2334 | Passed | 1h5m9s |
| Deploy baseline applications | 2336 | Passed | 3m11s |
| Upgrade applications | 2338 | Passed | 3m45s |

Controller timestamps independently verify the intended dependencies: all four
creations finished before Windows basics; activation finished before preparation;
both imports finished before the cutoff; both patch jobs started after the cutoff
and overlapped; baseline applications waited for both patch jobs; upgrades waited
for baseline installation.

## Verified final state

| Evidence | Server 2022 | Server 2025 |
|---|---|---|
| OS build | 20348.5020 | 26100.32690 |
| OS cumulative update | KB5082142 | KB5082063 |
| Applicable .NET component | KB5082427, under bundle KB5084071 | KB5082417 |
| VM memory allocation | 4096 MiB | 4096 MiB |
| Applicable approved updates remaining | 0 | 0 |
| Pending reboot after patching | No | No |
| Patch restarts, by System record order | 2 | 4 |
| Chocolatey CLI | 2.7.4 | 2.7.4 |
| Final 7-Zip package | 26.4.0 | 26.4.0 |
| Final Git package | 2.56.0.2 | 2.56.0.2 |

Both VM creation commands specified 4096 MiB. Final libvirt definitions each
allocate 4,194,304 KiB. Windows reports approximately 4095.5 and 4028.4 MiB visible
respectively, reflecting reserved memory. Guest clock offsets make System record
order and Controller timestamps safer than direct cross-host timestamp comparison.

Activation job 2311 reported the fresh Server 2025 clone initially unlicensed,
then licensed with its original topology verified after temporary connectivity
cleanup. The three Server 2022 clones were already licensed and skipped changes.
The normal fresh activation path is now verified live.

The internal April policy was verified with four selected OS/.NET bundles,
automatic approval rules disabled, no pending license acceptances and zero missing
payload bytes. Both patch artifacts verify the managed source and final empty scan.
External synchronization and the internal-only cutoff were separate stages.

Baseline job 2336 verified 7-Zip 26.03 and Git 2.55.0.windows.5 on both hosts.
Upgrade job 2338 verified 26.04 and 2.56.0.windows.2. Their pinned package versions
are recorded above. A final authenticated read of internal Nexus found all four
expected versions in the separate baseline/current feeds. Both endnodes have only
the internal current source configured; the public community source is absent.

## Preservation and monitoring

A final read-only comparison against baseline 2288 passed after the complete
workflow: the seven unrelated VM definitions/states and both Windows base-image
size/inode/mtime records match. The domain-name set is unchanged, and all four
rebuilt Windows VMs are running. The pre-deployment teardown check separately
proved the old clone disks absent before new storage was created.

During monitoring, MCP reported an invalid/expired token while a controller read
returned HTTP 502. Access later recovered with the same configured token; no
authentication or security settings were changed. The workflow continued
independently and its final AAP evidence confirms all 21 nodes succeeded.

## Post-run corrections

The standalone assessment template initially had no Machine credential attached;
jobs 2340/2342 could not authenticate. The controller configuration now applies
the existing Windows Machine and Vault credentials to both update and assessment
templates. Protected assessment job 2344 then read both installed baselines.

That later assessment found a Windows reboot marker on Server 2025, after the
workflow's patch jobs had reported clean completion. Application tasks previously
considered installer exit codes alone. The shared release task now also honors
explicit module reboot flags and CBS/Windows Update reboot markers, completes a
required reboot, and waits for both markers to clear before declaring application
success. Five regression tests exercise seven production-control-flow scenarios,
including clean skips, each reboot signal and refusal of uncleared markers.
The corrected application stage and final assessment will be rerun independently.


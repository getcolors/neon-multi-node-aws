# Native Red and Blue live verification

The 2026-09-10 verification uses the public package, copied installed launchers,
and the same desired state as the original Green deployment. Red uses Bun;
Blue uses Python/uv. Both delegate all five machines and their network to the
native matching `colors-compute` implementation. Operations are serialized
because the three runtimes intentionally share one profile and state layout.

## Lifecycle matrix

| Cycle | Fresh create | Reconverge | Recovery | Teardown |
| --- | --- | --- | --- | --- |
| 1 | Red passed | Blue passed | Blue passed | Blue passed; independent absence and repeat passed |
| 2 | Blue passed | Red passed | Red passed | Red passed; independent absence and Red/Blue repeats passed |

Cycle 1 starts from an empty AWS/DNS/local inventory. Red created five machines,
five encrypted root volumes, the shared network, managed SSH keypair, a managed
S3 state bucket, a separate native Neon S3 bucket and scoped IAM credentials,
and a Cloudflare DNS-only record. Both server acceptance and eight independent
public SQL/TLS/SSH gates passed. Blue convergence preserved all five instance
IDs, all five volume IDs, all six container IDs/images/creation times, and the
exact random witness originally written through the external TLS endpoint.
See `cycle1-cross-runtime-continuity.json` and `cycle1-public-blue.txt`.

Blue recovery replaced compute, stopped each safekeeper individually while
recording unique acknowledged writes, stopped two safekeepers, restarted the
broker, removed pageserver local cache and reattached from S3, and rebuilt one
safekeeper from empty local storage using the surviving two. The no-quorum
client probe withheld acknowledgement for 45.182715 seconds. Its uncertain row
was actually present after recovery: timeout does not establish rollback.
All three acknowledged outage witnesses and the original external witness
survived, with S3 attachment generation advancing to 2. See `cycle1-recovery.json`,
`cycle1-public-recovered.txt`, and `blue-rehearse-1-ansible.txt`.

The default Blue delete refused with exit 2 before provider/state operations.
Authorized deletion stopped writers on all five hosts before deleting storage.
Independent checks found zero remaining resources, zero remaining billable
resources, both buckets explicitly absent, all recorded EBS volumes gone,
no scoped IAM user, no DNS record, and no owned SSH keys or aliases.
Repeated Blue deletion passed without recreating resources.

Cycle 2 recreated the fully retired profile using Blue. Red reconvergence then
preserved the new lifecycle's five instances, five root disks, six containers
and exact external SQL witness. Both fresh create and reconvergence passed
seven built-in external gates and all eight independent public gates. See
`cycle2-cross-runtime-continuity.json` and `cycle2-public-red.txt`.

Red's full recovery sequence passed the same fault set. Independent readback
verified three unique acknowledged outage witnesses and the original cycle 2
external witness, with S3 generation 2. The no-quorum wait was 45.132080 seconds;
its uncertain row was present after recovery. These witnesses belong to this
fresh database and are not combined with those of cycle 1 or the original Green
run. See `cycle2-recovery.json`, `cycle2-no-quorum.json`,
`cycle2-public-recovered.txt`, and `red-rehearse-2-ansible.txt`.

The Red default-delete guard returned 2. Authorized teardown completed with
current-run writer-stop proof on all five hosts and managed backend retirement
last. Independent resource/DNS/local audits passed after deletion and again after
successful repeated deletion through both Red and Blue. Both audits count zero
remaining resources and zero billable resources, verify all five recorded EBS
volumes absent, both buckets explicitly absent, and no IAM/VPC/DNS/SSH artifacts.
See `cycle2-resources-after-repeat.json`, `cycle2-dns-after-repeat.json`,
`cycle2-local-after-repeat.json`, and both `*-delete-repeat-2.txt` logs.

The test deployment is no longer running. Provider credentials remain only in
ignored private environment files for future authorized use.

## Corrections found during native implementation

A child-process timeout could return -1 and a signal could return -15 from the
old SDK execution boundary, while workflow and Terraform failure checks only
recognized positive codes. Offline reproductions showed a failed Blue command
and interrupted destroy could be reported as success. Both SDK execution
boundaries now normalize timeout to 124 and signals to 128 plus signal number.
Actual child timeout/signal and fake-Terraform interruption regressions passed;
interrupted destroy retains rendered files. This was an offline discovery and
regression test, not an injected live cloud failure. See `sdk-verification.json`
and both `*-sdk-tests.txt` files.

A fresh Red launcher intermittently failed to resolve immutable Git dependencies
under Bun 1.3.10: `red: could not resolve dependencies`, followed by pinned
`colors-compute-red` and `red` resolution failures. Standalone fresh-cache runs
also reproduced the failure. The launcher now resolves the same immutable Git
SHAs through GitHub codeload archives for dependencies and overrides, and
publishes its staged cache only after successful installation. Eight isolated
cold-cache runs passed. This is a verified workaround; no claim is made about
Bun's internal cause. The initial failure is retained in `red-build.txt`.

## Pins and offline validation

- Live native package source: `038e93d524552ef36fb0fff5f306352e68283bff`.
- Final documentation source: `1eb421263e0aa2b6552948355c7591a1c749dae6`;
  public launcher head `413eec3a863744a6a53ea1b552461b983ce7bafb` stamps that
  source in all three payloads. Application code, resources, and dependency
  manifests are unchanged from the live-tested source. The final installed
  payloads were fetched with `npx skills add`, copied byte-identically, and
  tested with isolated cold caches; see `published-final-launchers.txt`.
- Red SDK: `7636bee6a7575485ebaf621f4b1834bdcea59738`.
- Blue SDK: `e29a7fc5a7a2895eacb882fc65520c2cdbab96c9`.
- Direct compute: `09ec539e75dc21c4dafb019eb8f9da276e695f6f`.
- Green SDK and pinned Neon/ONCE/image set retain the original tested versions.
- Public cold-cache launchers build and dry-run all lifecycle verbs without
  credentials or working-tree overrides. Both SSH modes produce identical
  28-file application trees in all three runtimes.
- Green: 14 tests/96 assertions; common Python runtime: 8 tests; Red: 13 tests/61
  assertions and typecheck; Blue: 16 tests. All pass.
- Red and Blue SDKs each pass 102 tests with one optional Floci test skipped.
- Workspace compute-copy contracts: 89 passed, zero failures.

Raw detailed Ansible traces are retained only after checking against actual
provider and application credentials. Provider credentials remain ignored.

## Limits

This is a five-machine, single-AZ functional deployment. Three safekeepers
provide WAL quorum; compute and pageserver have no automatic failover. The
cache rebuild test uses S3 and surviving WAL, and does not establish an RPO for
complete loss of every storage member. No cross-AZ availability claim is made.

## Catalog publication

Public package `413eec3`, Context Skill `ea584de`, and website `8ff77ac`
were pushed to main. The package remains featured and now exposes Red, Green,
and Blue runtime choices. The website passed typecheck (47 files, zero issues),
a 153-page build, both architecture image builds, and production deployment in
[CI run 34501822386](https://github.com/getcolors/colors-website/actions/runs/34501822386).

Live checks on `https://www.getcolors.ai` returned HTTP 200 for the package,
Red and Blue routes, updated context and featured page, plus their social cards.
All four downloaded skill archives matched their committed content hashes; each
package payload contains the final source pin and the context archive contains
the complete second-cycle recovery and cleanup proof. See
`website-live-verification.json` and `website-ci.json`.

The initial Python urllib probe received HTTP 403; curl subsequently fetched and
validated all required routes and archives. This records client-specific observed
behavior, not a diagnosed website defect.

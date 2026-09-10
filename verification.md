# Live verification: Neon Multi-Node AWS

The native Red/Blue verification is recorded separately in
[`evidence/red-blue/README.md`](evidence/red-blue/README.md). The report below
preserves the original Green lifecycle and its corrections.

Verified on 2026-09-10: live deployment, reconvergence, recovery, complete
teardown and repeated deletion passed. Final independent audits report zero
remaining deployment resources and zero remaining billable resources. Both
repositories are public; the deployment is no longer running.

The deployment uses five independent EC2 machines with separate encrypted root
volumes in one AWS availability zone. Two owned S3 buckets separate Terraform
state from Neon data. Scope and resource names are defined in `colors.yml`.

## Completed checks

- Empty initial inventory: no target machines, buckets, keypair or DNS record.
- All five machines provisioned through `colors-compute` fan-out and join.
- Native S3 managed backend and Neon bucket created during the lifecycle.
- Three role security groups: SSH/client database restricted to operator CIDR;
  pageserver, broker and WAL peers restricted to observed private /32 addresses.
- Independent network audit: public management endpoints unreachable; safekeeper
  cannot reach compute's PostgreSQL client port.
- Default delete refused with exit 2 before provider/state work.
- Package build, both SSH modes, golden and syntax checks, runtime tests, and
  copied published launcher in an empty credential environment pass.
- Server acceptance: authenticated SQL, specific authentication/privilege and
  plaintext refusals, all three safekeepers caught up to compute's flush LSN,
  newly uploaded WAL beyond a pre-switch baseline, pageserver objects, and
  ownership-marker write/readback.
- Independent public client: trusted certificate and matching DNS name with
  `sslmode=verify-full`, encrypted session, the negative gates above, a random
  persistent witness, a deterministic smoke row, and all six SSH aliases.
- Both S3 buckets block public access and use encryption. The application IAM
  credential can access Neon data but cannot list or read Terraform state.
- Fourth create retained all five instance IDs, five volume IDs, and six
  container IDs and creation timestamps. The exact random external witness
  remained unchanged. See `evidence/continuity-create-4.json` and
  `evidence/public-create-4.txt`.

## Live corrections

First create failed at application readiness. The database reported
`server does not support SSL, but SSL was required`; `SHOW ssl` returned `off`.
Certificate issuance had succeeded, but pinned Neon compute requires
`spec.features: ["tls_experimental"]` before it honors `compute_ctl_config.tls`.
Enabling that feature exposed a second failure:
`could not create key file error=unknown TLS key type`. The helper's certificate
signature check rejects the issued ECDSA-SHA384 chain. The final implementation
uses PostgreSQL's native `ssl`, `ssl_cert_file`, and `ssl_key_file` settings;
the third create passed both server and public trusted-TLS checks.

The first recovery rehearsal reached an acknowledged write with one safekeeper
stopped, then failed an assertion before recording its witness. `psql` printed
the returned value followed by an `INSERT 0 1` command tag, and the helper took
the last line. A read-only diagnosis confirmed the row existed. The fix uses
`psql -q`; the failed run is not a passing recovery test. The playbook restored
the stopped safekeeper in its `always` block.

## Recovery results

The second rehearsal replaced compute, stopped and restored each safekeeper in
turn, withheld write acknowledgement with two safekeepers stopped, restarted the
broker, removed the pageserver tenant cache and reattached from S3 with surviving
WAL, then rebuilt one safekeeper from empty local storage. Each stage checked
retained witnesses before the ordinary smoke gate could rewrite its row.

Independent public TLS queries read back all three unique, acknowledged outage
witnesses and the original external random witness. S3 attachment generation
advanced from 1 to 2. The `uncertain-quorum` write was present after recovery:
the timed-out client did not establish rollback. Evidence lives in
`evidence/recovery-rehearsal-2.json` and `evidence/public-rehearsal-2.txt`.

The third rehearsal retained a detailed Ansible trace because the ordinary
launcher omits successful playbook stdout. `evidence/ansible-rehearsal-3.txt`
records a 45.142796-second no-acknowledgement probe and each stop, restore, cache
removal, empty-member rebuild and acceptance result. Final independent checks
retained all six acknowledged outage witnesses and the external witness;
attachment generation reached 3. See `evidence/recovery-final.json`,
`evidence/public-final-live.txt`, `evidence/services-final-live.json` and
`evidence/storage-final-live.json`. The third timeout reused the uncertain row;
its later presence does not independently prove that third attempt committed.

To retain a future rehearsal trace, set `ANSIBLE_LOG_PATH` to an ignored absolute
path and `ANSIBLE_VERBOSITY=1` when running the published `./green rehearse`.
Review logs for credentials before publication.

## Offline validation

The package passed 14 Clojure tests with 96 assertions and eight Python runtime
tests. Both SSH key modes rendered 28-file golden trees and passed Ansible syntax
checks. The copied public launcher built and dry-ran all four operation verbs
outside its checkout with an empty credential environment. The workspace audit
passed 87 compute copy contracts; see `evidence/compute-contracts.txt` and
`evidence/launcher-published-final.txt`.

## Cleanup correction

The first delete failed before stopping writers or deleting cloud resources:
the runner reported that it could not execute `ansible-playbook` in a missing
working directory. The executable was installed. Green's scaffold interprets
`:green/event :delete` as removing its target files; the package had passed that
event before trying to execute the cleanup playbook. Source `583424b` renders
the files using the build event, then restores the delete event for execution
and mandatory writer proof. The second delete passed the writer-stop stage
on all five hosts. See `evidence/delete-render-diagnosis.txt`,
`evidence/live-delete-1.txt` and `evidence/writer-stop-evidence.txt`.

The third delete, a repeat after complete retirement, exposed another safe
failure: journal inspection treats `NoSuchKey` as absent but the deleted bucket
returns `NoSuchBucket`. The generic error incorrectly suggested legacy state
migration. Source `418cb97` routes managed delete inspection failures to the
existing backend finalizer, which independently authenticates the caller,
checks expected bucket ownership and absence, and refuses inaccessible,
unowned or live state. It does not turn inspection errors into success.
The fourth delete passed through that authority without recreating resources.
See `evidence/journal-after-retirement.txt`, `evidence/live-delete-3.txt` and
`evidence/live-delete-4.txt`.

## Final absence audit

`evidence/resources-after-delete.json` and
`evidence/resources-after-repeat-delete.json` independently verify:

- All five recorded instances terminated and all five recorded EBS volumes absent.
- Both S3 buckets return explicit 404 responses; scoped application IAM is absent.
- No owned VPC, subnet, route table, gateway, security group, network interface,
  network ACL or provider keypair remains.
- Remaining resource count and remaining billable resource count are both zero.

`evidence/dns-after-repeat-delete.json` verifies the Cloudflare record is absent.
`evidence/local-after-repeat-delete.json` verifies the owned SSH keys, six aliases
and managed configuration block are absent. Provider credentials remain only in
the ignored private environment files for future authorized work.

The tested application runtime is `9108620`, the first complete cleanup is
`583424b`, and final repeated-delete handling is `418cb97`; the final public
launcher at `0f06fe9` pins `418cb97`. The latter changes affect lifecycle handling;
the verified application runtime files are unchanged.

## Limits

This five-machine, single-zone topology is not complete application HA. Compute
and pageserver have no automatic failover. Recovery and quorum behavior require
observable witness checks, not an inference from running containers or S3 listings.

# Neon Multi-Node on AWS

Public deployment profile for the [Neon Multi-Node Package Skill](https://github.com/getcolors/neon-multi-node).
Five Ubuntu 24.04 machines in `us-east-1a`: compute, pageserver with storage broker,
and three safekeepers. Compute and pageserver use `t3.large`; safekeepers use
`t3.medium`. Each machine has an encrypted 40 GiB root disk.

The package creates its own S3 Terraform backend bucket, Neon S3 bucket, scoped
IAM credentials, SSH keypair, role firewalls and Cloudflare DNS record. Native
PostgreSQL TLS uses `neon-multi-node-aws.bigconfig.online:55433`; DNS is unproxied,
and SSH/database access is restricted to the configured operator CIDR.

## Commands

Choose `./green` (Babashka), `./red` (Bun), or `./blue` (uv/Python). All three
use this profile's same `colors.yml`, SSH aliases and Terraform state. Run one
lifecycle operation at a time. For example, replace `green` below with `red`
or `blue` to use that runtime.

```sh
./green build
./green create --dry-run
./green create
./green describe
python3 check_public.py
./green rehearse
python3 check_public.py --continuity
python3 check_recovery.py
COLORS_PAR_COMPUTE_PREVENT_DESTROY=false ./green delete
python3 evidence/check_resources.py --expect-absent
python3 check_dns.py --expect-absent
python3 check_local_cleanup.py
```

The delete command destroys the database and both buckets. Committed desired state
retains destruction protection. Credentials belong in ignored `.envrc.private`,
loaded by `.envrc`; never commit provider credentials or `.colors/` state.
AWS credentials use the ambient chain, and DNS uses
`COLORS_PAR_CLOUDFLARE_API_TOKEN`. Never export `COLORS_PAR_PROFILE`.

Load `.envrc` before commands that need provider credentials. The installed
launcher pins the published implementation; no local library override is needed.

`check_public.py` is an independent operator-path test: trusted TLS, hostname,
SQL witness continuity, specific authentication and plaintext refusals, privilege
isolation and every generated SSH alias. `check_dns.py` inspects the exact
Cloudflare record. `evidence/check_resources.py` inventories cloud resources and
records exact root-volume IDs for the final absence audit.
`check_storage.py` checks native S3 objects and denies the application credential
access to the state bucket. `check_network.py` checks actual ingress and denied
connections; `check_services.py` checks every container against its desired image
digest. `check_recovery.py` verifies every acknowledged outage witness and records
the uncertain write's actual post-recovery outcome. A client timeout does not
establish rollback. `check_continuity.py` compares saved container and resource
identities across convergence; its input filenames are configurable.

Reusing this profile after cleanup requires clearing or archiving its prior
local evidence deliberately; a new deployment should have its own profile and
new fixed tenant/timeline identities. Never reuse an active deployment's profile
against a different state bucket.

For separate lifecycle evidence, `check_public.py --witness-file <path>` and
`evidence/check_resources.py --baseline <path>` preserve each run's exact witness
and resource inventory. Reuse the same paths for continuity and absence checks
within that lifecycle. The red/blue verification is recorded under
`evidence/red-blue/`; the original Green evidence remains unchanged.

This is a single-AZ functional deployment. Three separate safekeeper machines
provide WAL quorum; compute and pageserver have no automatic failover. Storage
recovery results and limitations are documented in verification evidence, not
inferred from container status or the presence of historical S3 objects.

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

```sh
./green build
./green create --dry-run
./green create
./green describe
python3 check_public.py
./green rehearse
python3 check_public.py --continuity
COLORS_PAR_COMPUTE_PREVENT_DESTROY=false ./green delete
```

The last command destroys the database and both buckets. Committed desired state
retains destruction protection. Credentials belong in ignored `.envrc.private`,
loaded by `.envrc`; never commit provider credentials or `.colors/` state.
AWS credentials use the ambient chain, and DNS uses
`COLORS_PAR_CLOUDFLARE_API_TOKEN`. Never export `COLORS_PAR_PROFILE`.

`check_public.py` is an independent operator-path test: trusted TLS, hostname,
SQL witness continuity, specific authentication and plaintext refusals, privilege
isolation and every generated SSH alias. `check_dns.py` inspects the exact
Cloudflare record. `evidence/check_resources.py` inventories cloud resources and
records exact root-volume IDs for the final absence audit.

Reusing this profile after cleanup requires clearing or archiving its prior
local evidence deliberately; a new deployment should have its own profile and
new fixed tenant/timeline identities. Never reuse an active deployment's profile
against a different state bucket.

This is a single-AZ functional deployment. Three separate safekeeper machines
provide WAL quorum; compute and pageserver have no automatic failover. Storage
recovery results and limitations are documented in verification evidence, not
inferred from container status or the presence of historical S3 objects.

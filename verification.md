# Live verification: Neon Multi-Node AWS

Build in progress on 2026-09-10. This file records completed observations;
application success and recovery are not yet claimed.

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

## Live corrections

First create failed at application readiness. The database reported
`server does not support SSL, but SSL was required`; `SHOW ssl` returned `off`.
Certificate issuance had succeeded, but pinned Neon compute requires
`spec.features: ["tls_experimental"]` before it honors `compute_ctl_config.tls`.
The corrected package is being tested through its published launcher.

This five-machine, single-zone topology is not complete application HA. Compute
and pageserver have no automatic failover. Recovery and quorum behavior require
observable witness checks, not an inference from running containers or S3 listings.

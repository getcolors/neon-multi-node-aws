"""Read-only external verification of acknowledged outage writes and S3 generation."""
import json
import os
from pathlib import Path
import re
import subprocess
import time
import boto3
import yaml

cfg = yaml.safe_load(Path(__file__).with_name('colors.yml').read_text())
profile = cfg['profile']

def read_remote(path):
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', profile, 'sudo', '-n', 'cat', path],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, 'Remote recovery evidence unavailable: ' + path
    return result.stdout.strip()

records = json.loads(read_remote('/etc/neon/rehearsal-witnesses.json'))
assert isinstance(records, list) and len(records) >= 3, 'Fewer than three acknowledged outage witnesses'
expected_members = {'safekeeper-0', 'safekeeper-1', 'safekeeper-2'}
assert {r['member'] for r in records} == expected_members, 'Rehearsal did not cover exactly all safekeepers'
assert len({r['id'] for r in records}) == len(records), 'Outage witness IDs are not unique'
for record in records:
    assert re.fullmatch(r'quorum-[0-9a-f]{32}', record['id']), 'Invalid witness ID'
    assert re.fullmatch(r'[0-9a-f]{32}', record['value']), 'Invalid witness payload'

password = read_remote('/etc/neon/secrets/neon_role_password')
assert password, 'Missing application credential'
env = {k: v for k, v in os.environ.items() if not k.startswith('PG')}
env.update(PGHOST=cfg['neon-host'], PGPORT='55433', PGDATABASE=cfg['neon-database'],
           PGUSER=cfg['neon-role'], PGPASSWORD=password, PGPASSFILE='/dev/null',
           PGCONNECT_TIMEOUT='10', PGSSLMODE='verify-full',
           PGSSLROOTCERT='/etc/ssl/certs/ca-certificates.crt')

def sql(query):
    result = subprocess.run(['psql', '-X', '-A', '-t', '-w', '-v', 'ON_ERROR_STOP=1', '-c', query],
                            env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, 'External recovery SQL query failed'
    return result.stdout.strip()

assert sql('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()') == 't', 'Recovery query lacks TLS'
for record in records:
    assert sql("SELECT value FROM public.colors_witness WHERE id='" + record['id'] + "'") == record['value'], 'Acknowledged outage write was lost'
# A timed-out write may later commit. Record observation; neither outcome is a failure.
uncertain_rows = json.loads(sql("SELECT coalesce(json_agg(value), '[]'::json)::text FROM public.colors_witness WHERE id='uncertain-quorum'"))
assert isinstance(uncertain_rows, list) and len(uncertain_rows) <= 1, 'Unexpected uncertain-write row count'

creds = dict(line.split('=', 1) for line in read_remote('/etc/neon/r2.env').splitlines())
s3 = boto3.client('s3', region_name=cfg['neon-r2-region'],
                  aws_access_key_id=creds['AWS_ACCESS_KEY_ID'],
                  aws_secret_access_key=creds['AWS_SECRET_ACCESS_KEY'])
key = cfg['neon-r2-prefix'] + '/.colors-generation'
raw = s3.get_object(Bucket=cfg['neon-r2-bucket'], Key=key)['Body'].read().decode().strip()
assert re.fullmatch(r'[0-9]+', raw), 'Invalid remote attachment generation'
generation = int(raw)
assert generation >= 2, 'Remote attachment generation did not advance beyond initial generation'
print(json.dumps({'profile': profile, 'checked_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  'trusted_external_tls': True, 'acknowledged_witnesses': records,
                  'acknowledged_witnesses_verified': len(records), 'members_covered': sorted(expected_members),
                  'uncertain_write_observed': {'present': bool(uncertain_rows), 'values': uncertain_rows,
                      'interpretation': 'Observed after recovery; a timeout did not establish commit or rollback.'},
                  's3_attachment_generation': generation, 'verified': True}, indent=2))

"""Independent operator-path SQL/TLS gates; emits no credentials."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--continuity', action='store_true', help='Require the previously recorded witness unchanged')
parser.add_argument('--witness-file', type=Path, help='Evidence path for this deployment lifecycle; defaults to evidence/continuity.json')
args = parser.parse_args()
root = Path(__file__).resolve().parent
cfg = yaml.safe_load((root / 'colors.yml').read_text())
profile = cfg['profile']
read = subprocess.run(['ssh', '-o', 'BatchMode=yes', profile, 'sudo', '-n', 'cat', '/etc/neon/secrets/neon_role_password'], capture_output=True, text=True, timeout=30)
assert read.returncode == 0 and read.stdout.strip(), 'Cannot read operator credential through managed SSH alias'
password = read.stdout.strip()
base = {k:v for k,v in os.environ.items() if not k.startswith('PG')}
base.update(PGHOST=cfg['neon-host'], PGPORT='55433', PGUSER=cfg['neon-role'], PGDATABASE=cfg['neon-database'], PGCONNECT_TIMEOUT='10', PGPASSFILE='/dev/null', PGSSLMODE='verify-full', PGSSLROOTCERT='/etc/ssl/certs/ca-certificates.crt')
def sql(query, secret=password, sslmode='verify-full', expect=True):
    env = dict(base, PGSSLMODE=sslmode)
    if secret is not None: env['PGPASSWORD'] = secret
    run = subprocess.run(['psql','-X','-A','-t','-w','-v','ON_ERROR_STOP=1','-c',query], env=env, capture_output=True, text=True, timeout=40)
    if expect and run.returncode:
        raise AssertionError('SQL gate failed: '+run.stderr.replace(password,'[redacted]'))
    return run

gates = []
def passed(name):
    gates.append(name)
    print('PASS '+name, flush=True)

assert sql('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').stdout.strip() == 't'
passed('trusted TLS certificate, matching DNS name, encrypted PostgreSQL session')
for label,secret,mode,expected in [
    ('wrong password refused', 'invalid-'+secrets.token_hex(12), 'verify-full', 'password authentication failed'),
    ('passwordless connection refused', None, 'verify-full', 'no password supplied'),
    ('plaintext connection refused', password, 'disable', 'pg_hba.conf rejects connection')]:
    r=sql('SELECT 1',secret,mode,False)
    assert r.returncode != 0 and expected in r.stderr, label+': expected specific refusal, not arbitrary failure'
    passed(label)
r=sql('ALTER ROLE '+cfg['neon-role']+' WITH SUPERUSER',expect=False)
assert r.returncode != 0 and ('permission denied' in r.stderr or 'must be superuser' in r.stderr or 'Only roles with' in r.stderr), 'Application privilege escalation not specifically refused'
passed('application role cannot escalate to superuser')

witness_file=args.witness_file or root/'evidence'/'continuity.json'
if args.continuity:
    witness=json.loads(witness_file.read_text())
    assert witness['profile'] == profile
else:
    assert not witness_file.exists(), 'Witness already exists; use --continuity to preserve it'
    witness={'profile':profile,'key':secrets.token_hex(12),'payload':secrets.token_hex(64)}
    sql('CREATE TABLE IF NOT EXISTS colors_external_witness (id text PRIMARY KEY, payload text NOT NULL)')
    sql("INSERT INTO colors_external_witness VALUES ('"+witness['key']+"','"+witness['payload']+"')")
    witness_file.write_text(json.dumps(witness,indent=2)+'\n')
r=sql("SELECT payload FROM colors_external_witness WHERE id='"+witness['key']+"'")
assert r.stdout.strip() == witness['payload'], 'Persisted witness differs'
passed('exact persistent witness read through external TLS endpoint')
sql("CREATE TABLE IF NOT EXISTS colors_external_smoke (id integer PRIMARY KEY, counter integer NOT NULL); INSERT INTO colors_external_smoke VALUES (1,1) ON CONFLICT (id) DO UPDATE SET counter=colors_external_smoke.counter+1")
assert sql('SELECT count(*) FROM colors_external_smoke').stdout.strip() == '1'
passed('authenticated write/read with one deterministic smoke row')
for suffix in ['', '-compute-0', '-pageserver-0', '-safekeeper-0', '-safekeeper-1', '-safekeeper-2']:
    r=subprocess.run(['ssh','-o','BatchMode=yes',profile+suffix,'true'],capture_output=True,timeout=30)
    assert r.returncode == 0, 'SSH alias unavailable: '+profile+suffix
passed('entry and all five generated node SSH aliases')
print(json.dumps({'profile':profile,'gates':gates,'passed':len(gates),'continuity':args.continuity,'checked_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())},indent=2))

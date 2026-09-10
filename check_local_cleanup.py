"""Verify owned local SSH keys and aliases are absent after cloud teardown."""
import json
from pathlib import Path
import yaml

cfg = yaml.safe_load(Path(__file__).with_name('colors.yml').read_text())
profile = cfg['profile']
ssh = Path.home() / '.ssh'
paths = [ssh / (profile + suffix) for suffix in ('', '.pub', '.known_hosts')]
assert all(not p.exists() and not p.is_symlink() for p in paths), 'Owned SSH material remains'
config = (ssh / 'config').read_text() if (ssh / 'config').exists() else ''
assert '# BEGIN ' + profile + ' ANSIBLE MANAGED BLOCK' not in config, 'Managed SSH block remains'
aliases = {profile + suffix for suffix in ('', '-compute-0', '-pageserver-0',
                                         '-safekeeper-0', '-safekeeper-1', '-safekeeper-2')}
for line in config.splitlines():
    fields = line.split()
    if fields and fields[0].lower() == 'host':
        assert not aliases.intersection(fields[1:]), 'Owned SSH alias remains'
print(json.dumps({'profile': profile, 'owned_key_paths_absent': [str(p) for p in paths],
                  'aliases_absent': sorted(aliases), 'managed_block_absent': True,
                  'verified': True}, indent=2))

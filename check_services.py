"""Inspect every runtime container without reading its environment or secrets."""
import json,subprocess
from pathlib import Path
import yaml
cfg=yaml.safe_load(Path(__file__).with_name('colors.yml').read_text())
roles=['compute-0','pageserver-0','safekeeper-0','safekeeper-1','safekeeper-2']; rows=[]
for role in roles:
    alias=cfg['profile']+'-'+role
    cmd="sudo -n docker ps -a --filter label=com.docker.compose.project=neon --format '{{.ID}}'"
    r=subprocess.run(['ssh','-o','BatchMode=yes',alias,cmd],capture_output=True,text=True,timeout=30)
    assert r.returncode==0, 'Host inspection failed: '+alias
    ids=r.stdout.split()
    assert len(ids)==(2 if role=='pageserver-0' else 1), 'Unexpected container count: '+alias
    containers=[]
    for ident in ids:
        fmt='{{json .State}}|{{json .Config.Image}}|{{json .Image}}|{{json .RestartCount}}|{{json .Created}}|{{json .Name}}'
        r=subprocess.run(['ssh','-o','BatchMode=yes',alias,'sudo','-n','docker','inspect','--format',"'"+fmt+"'",ident],capture_output=True,text=True,timeout=30)
        assert r.returncode==0, 'Container inspection failed'
        state,image,digest,restarts,created,name=map(json.loads,r.stdout.strip().split('|'))
        expected_image=cfg['neon-compute-image'] if role=='compute-0' else cfg['neon-image']
        assert image==expected_image, 'Container image differs from desired immutable pin: '+alias
        assert state['Status']=='running' and state.get('Health',{}).get('Status') != 'unhealthy', 'Container status or healthcheck failed: '+alias
        assert state['Running'] and not state['Restarting'] and not state['OOMKilled'], 'Unhealthy container: '+alias
        containers.append({'id':ident,'name':name,'image':image,'digest':digest,'created':created,'restarts':restarts,'state':state['Status']})
    rows.append({'alias':alias,'containers':containers,'healthy':True})
print(json.dumps({'profile':cfg['profile'],'healthy':True,'hosts':rows},indent=2))

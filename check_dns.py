"""Read Cloudflare DNS without exposing its credential."""
import argparse,json,os,urllib.request,subprocess,socket
from pathlib import Path
import yaml
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--expect-absent',action='store_true');a=p.parse_args()
cfg=yaml.safe_load(Path(__file__).with_name('colors.yml').read_text())
def get(path):
    req=urllib.request.Request('https://api.cloudflare.com/client/v4/'+path,headers={'Authorization':'Bearer '+os.environ['COLORS_PAR_CLOUDFLARE_API_TOKEN']})
    with urllib.request.urlopen(req,timeout=30) as r: result=json.load(r)
    assert result['success'], 'Cloudflare lookup failed'
    return result['result']
z=get('zones?name='+cfg['cloudflare-zone']);assert len(z)==1
records=get('zones/'+z[0]['id']+'/dns_records?name='+cfg['neon-host'])
if a.expect_absent: assert len(records)==0, 'DNS record remains'
else:
    assert len(records)==1 and records[0]['type']=='A' and records[0]['proxied'] is False, 'Expected one DNS-only A record'
    ssh=subprocess.run(['ssh','-G',cfg['profile']],capture_output=True,text=True,timeout=10)
    assert ssh.returncode==0, 'Cannot inspect generated entry alias'
    expected=next(line.split(None,1)[1] for line in ssh.stdout.splitlines() if line.startswith('hostname '))
    assert records[0]['content']==expected and socket.gethostbyname(cfg['neon-host'])==expected, 'DNS API or resolver does not match the generated compute entry address'
print(json.dumps({'domain':cfg['neon-host'],'records':[{k:r[k] for k in ['id','name','type','content','proxied']} for r in records],'verified':True},indent=2))

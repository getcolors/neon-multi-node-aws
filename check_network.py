"""Read AWS rules and independently probe allowed and forbidden role paths."""
import concurrent.futures,json,socket,subprocess
from pathlib import Path
import boto3,yaml
cfg=yaml.safe_load(Path(__file__).with_name('colors.yml').read_text()); ec2=boto3.client('ec2',region_name=cfg['aws-region']);profile=cfg['profile']
r=ec2.describe_instances(Filters=[{'Name':'tag:Name','Values':[profile+'-*']},{'Name':'instance-state-name','Values':['running']}])
nodes={next(t['Value'] for t in i['Tags'] if t['Key']=='Name').removeprefix(profile+'-'):i for x in r['Reservations'] for i in x['Instances']}; assert len(nodes)==5
sgs=ec2.describe_security_groups(GroupIds=sorted({s['GroupId'] for i in nodes.values() for s in i['SecurityGroups']}))['SecurityGroups'];assert len(sgs)==3
for sg in sgs:
    for rule in sg['IpPermissions']:
        assert rule['IpProtocol']=='tcp' and rule['FromPort']==rule['ToPort']
        port=rule['FromPort'];src={r['CidrIp'] for r in rule.get('IpRanges',[])}
        if port==22:assert src==set(cfg['ssh-sources'])
        elif port==55433:assert src==set(cfg['postgres-sources'])
        elif port==80:assert src=={'0.0.0.0/0'}
        else:assert src and all(x.startswith('10.75.1.') and x.endswith('/32') for x in src)
checks=[]
def probe(node,port):
    try:
        with socket.create_connection((nodes[node]['PublicIpAddress'],port),timeout=2):return True
    except OSError:return False
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
    tasks={(node,port):pool.submit(probe,node,port) for node in nodes for port in [22,9898,6400,50051,5454,7676,3080]}
    for (node,port),future in tasks.items():
        reachable=future.result();assert reachable==(port==22), 'Unexpected public reachability '+node+':'+str(port)
        checks.append({'source':'operator','target':node,'port':port,'reachable':reachable})
# Prove one forbidden east-west route from an owned non-client role.
remote="import socket; s=socket.socket(); s.settimeout(3); print(s.connect_ex(('"+nodes['compute-0']['PrivateIpAddress']+"',55433)))"
r=subprocess.run(['ssh','-o','BatchMode=yes',profile+'-safekeeper-0','python3','-c',"'"+remote.replace("'","'\"'\"'")+"'"],capture_output=True,text=True,timeout=15)
assert r.returncode==0 and r.stdout.strip().isdigit() and r.stdout.strip()!='0', 'Safekeeper unexpectedly reached PostgreSQL client port'
checks.append({'source':'safekeeper-0','target':'compute-0','port':55433,'reachable':False})
print(json.dumps({'profile':profile,'security_groups':len(sgs),'checks':checks,'passed':True},indent=2))

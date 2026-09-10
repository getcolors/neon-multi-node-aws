"""Compare saved deployment observations; no network or live mutations."""
import argparse
import json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--before',default='services-before-create-4.json')
p.add_argument('--after',default='services-after-create-4.json')
p.add_argument('--resources',default='resources-verified-create.json')
a=p.parse_args()
root=Path(__file__).with_name('evidence')
def read(name):return json.loads((root/name).read_text())
baseline=read('resource-baseline.json');resources=read(a.resources)
assert baseline['profile']==resources['profile'] and baseline['region']==resources['region']
instances={i['id'] for i in resources['instances'] if i['state']=='running'}
volumes={v['id'] for v in resources['Volumes']}
assert len(instances)==5 and instances==set(baseline['instance_ids']), 'Instance identities changed'
assert len(volumes)==5 and volumes=={v['id'] for v in baseline['volumes']}, 'Volume identities changed'
assert {v['id'] for v in resources['Vpcs']}==set(baseline['vpc_ids']), 'VPC identity changed'
before=read(a.before);after=read(a.after)
assert before['profile']==after['profile']==baseline['profile']
def containers(report):
    assert report['healthy'] is True and len(report['hosts'])==5
    result={}
    for host in report['hosts']:
        assert host['healthy'] is True
        for container in host['containers']:
            key=(host['alias'],container['name'])
            assert key not in result and container['state']=='running'
            result[key]={field:container[field] for field in ('id','image','digest','created')}
    assert len(result)==6
    return result
old=containers(before);new=containers(after)
assert old==new, 'Container identity, image or creation time changed during convergence'
print(json.dumps({'profile':baseline['profile'],'source_files':[a.before,a.after,a.resources,'resource-baseline.json'],
                  'instance_ids':sorted(instances),'volume_ids':sorted(volumes),
                  'container_ids':[{ 'alias':k[0],'name':k[1],**v} for k,v in sorted(new.items())],
                  'same_five_instances':True,'same_five_volumes':True,'same_six_containers':True,'verified':True},indent=2))

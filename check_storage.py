"""Inspect bucket protections and prove scoped application credentials cannot read state."""
import json,os,subprocess
from pathlib import Path
import boto3,yaml
from botocore.exceptions import ClientError
cfg=yaml.safe_load(Path(__file__).with_name('colors.yml').read_text())
region=cfg['s3-region']; session=boto3.Session(region_name=region); account=session.client('sts').get_caller_identity()['Account']
s3=session.client('s3'); result={'profile':cfg['profile'],'buckets':[]}
for name in [cfg['s3-bucket'],cfg['neon-r2-bucket']]:
    pab=s3.get_public_access_block(Bucket=name,ExpectedBucketOwner=account)['PublicAccessBlockConfiguration'];assert all(pab.values())
    rules=s3.get_bucket_encryption(Bucket=name,ExpectedBucketOwner=account)['ServerSideEncryptionConfiguration']['Rules'];assert all(r['ApplyServerSideEncryptionByDefault']['SSEAlgorithm'] in ('AES256','aws:kms') for r in rules)
    tags={x['Key']:x['Value'] for x in s3.get_bucket_tagging(Bucket=name,ExpectedBucketOwner=account)['TagSet']};assert tags['colors:profile']==cfg['profile']
    result['buckets'].append({'name':name,'public_access_blocked':True,'encrypted':True,'ownership_tags':{k:v for k,v in tags.items() if k.startswith('colors:')}})
r=subprocess.run(['ssh','-o','BatchMode=yes',cfg['profile'],'sudo','-n','cat','/etc/neon/r2.env'],capture_output=True,text=True,timeout=30);assert r.returncode==0
creds=dict(line.split('=',1) for line in r.stdout.strip().splitlines())
app=boto3.client('s3',region_name=region,aws_access_key_id=creds['AWS_ACCESS_KEY_ID'],aws_secret_access_key=creds['AWS_SECRET_ACCESS_KEY'])
objects=[]
for page in app.get_paginator('list_objects_v2').paginate(Bucket=cfg['neon-r2-bucket'],Prefix=cfg['neon-r2-prefix']+'/'):
    objects.extend({'key':x['Key'],'size':x['Size']} for x in page.get('Contents',[]))
assert any('/pageserver/' in x['key'] for x in objects), 'No pageserver storage objects'
import re
wal=[x for x in objects if '/safekeeper/' in x['key'] and re.search(r'/[0-9A-F]{24}$',x['key'])]
assert wal, 'No closed WAL segments in S3'
for key in ['.colors-init','.colors-ready']:
    body=app.get_object(Bucket=cfg['neon-r2-bucket'],Key=cfg['neon-r2-prefix']+'/'+key)['Body'].read().decode()
    assert body==cfg['profile'], 'Ownership marker mismatch'
for action in ['list','read']:
    try:
        if action=='list':app.list_objects_v2(Bucket=cfg['s3-bucket'],MaxKeys=1)
        else:app.get_object(Bucket=cfg['s3-bucket'],Key=cfg['profile']+'/compute/shared.tfstate')
    except ClientError as e: assert e.response['Error']['Code']=='AccessDenied', 'Unexpected state isolation response'
    else:raise AssertionError('Application credential can access backend state')
result.update(application_objects=objects,closed_wal_segments=len(wal),ownership_markers_verified=True,application_state_list_denied=True,application_state_read_denied=True)
print(json.dumps(result,indent=2))

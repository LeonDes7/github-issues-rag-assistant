"""Scoped AWS teardown. Preview by default; never touches S3."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.config import Config
from dotenv import load_dotenv

REGION = 'us-east-2'
DB = 'github-rag-db'
NAT = 'nat-097cf07818b8577a9'
EIP = 'eipalloc-0634590d08739cedc'
CONFIRM = 'TEARDOWN github-rag-db'


def clients():
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    session = boto3.Session(region_name=REGION)
    config = Config(retries={'max_attempts': 0}, connect_timeout=10, read_timeout=30)
    return {name: session.client(name, config=config) for name in
            ('sts', 'rds', 'ec2', 'lambda', 'apigatewayv2', 'ecr', 'logs', 'secretsmanager')}


def pages(client, operation, key, **kwargs):
    if client.can_paginate(operation):
        return [item for page in client.get_paginator(operation).paginate(**kwargs) for item in page.get(key, [])]
    return getattr(client, operation)(**kwargs).get(key, [])


def inventory(c):
    db = c['rds'].describe_db_instances(DBInstanceIdentifier=DB)['DBInstances'][0]
    nat = c['ec2'].describe_nat_gateways(NatGatewayIds=[NAT])['NatGateways'][0]
    address = c['ec2'].describe_addresses(AllocationIds=[EIP])['Addresses'][0]
    if nat['State'] != 'available' or db['DBInstanceStatus'] != 'available':
        raise RuntimeError('Targets must be available; inspect partial/previous teardown manually')
    if db.get('DeletionProtection'):
        raise RuntimeError('RDS deletion protection is enabled; this script will not change it')
    if nat['VpcId'] != db['DBSubnetGroup']['VpcId']:
        raise RuntimeError('NAT and database VPC mismatch')
    if EIP not in [a.get('AllocationId') for a in nat['NatGatewayAddresses']]:
        raise RuntimeError('EIP is not attached to the approved NAT gateway')
    if address.get('AssociationId') not in [a.get('AssociationId') for a in nat['NatGatewayAddresses']]:
        raise RuntimeError('EIP association mismatch')
    remaining, errors = {}, {}
    queries = {
        'secrets': ('secretsmanager', 'list_secrets', 'SecretList', {}, ('Name', 'DeletedDate')),
        'ecr_repositories': ('ecr', 'describe_repositories', 'repositories', {}, ('repositoryName',)),
        'cloudwatch_logs': ('logs', 'describe_log_groups', 'logGroups', {}, ('logGroupName', 'storedBytes', 'retentionInDays')),
        'lambda': ('lambda', 'list_functions', 'Functions', {}, ('FunctionName', 'MemorySize', 'VpcConfig')),
        'api_gateway_http': ('apigatewayv2', 'get_apis', 'Items', {}, ('Name', 'ApiId')),
        'public_eips': ('ec2', 'describe_addresses', 'Addresses', {}, ('AllocationId', 'PublicIp', 'AssociationId')),
        'public_network_interfaces': ('ec2', 'describe_network_interfaces', 'NetworkInterfaces', {}, ('NetworkInterfaceId', 'Association', 'Description')),
        'other_rds_instances': ('rds', 'describe_db_instances', 'DBInstances', {}, ('DBInstanceIdentifier', 'DBInstanceStatus', 'DBInstanceClass', 'AllocatedStorage')),
        'rds_snapshots': ('rds', 'describe_db_snapshots', 'DBSnapshots', {}, ('DBSnapshotIdentifier', 'DBInstanceIdentifier', 'SnapshotType', 'Status', 'SnapshotCreateTime')),
    }
    for label, (service, op, key, kwargs, fields) in queries.items():
        try:
            rows = pages(c[service], op, key, **kwargs)
            if label == 'public_network_interfaces':
                rows = [row for row in rows if row.get('Association', {}).get('PublicIp')]
            remaining[label] = [{field: row[field] for field in fields if field in row} for row in rows]
        except Exception as exc:
            errors[label] = type(exc).__name__
    try:
        remaining['ecr_images'] = {repo['repositoryName']: [
            {k: row.get(k) for k in ('imageDigest', 'imageSizeInBytes', 'imageTags')}
            for row in pages(c['ecr'], 'describe_images', 'imageDetails', repositoryName=repo['repositoryName'])]
            for repo in remaining.get('ecr_repositories', [])}
    except Exception as exc:
        errors['ecr_images'] = type(exc).__name__
    restore = {
        'DBInstanceIdentifier': DB, 'DBInstanceClass': db['DBInstanceClass'],
        'DBSubnetGroupName': db['DBSubnetGroup']['DBSubnetGroupName'],
        'VpcSecurityGroupIds': [g['VpcSecurityGroupId'] for g in db['VpcSecurityGroups']],
        'PubliclyAccessible': db['PubliclyAccessible'], 'MultiAZ': db['MultiAZ'],
        'Port': db['Endpoint']['Port'], 'AutoMinorVersionUpgrade': db['AutoMinorVersionUpgrade'],
        'DBParameterGroupName': db['DBParameterGroups'][0]['DBParameterGroupName'],
    }
    return {
        'account': c['sts'].get_caller_identity()['Account'], 'region': REGION,
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'targets': {'rds': DB, 'nat': NAT, 'eip': EIP, 'public_ip': address['PublicIp'], 'vpc': nat['VpcId']},
        'snapshot': {'identifier': 'github-rag-db-manual-teardown-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S') + '-' + uuid4().hex[:8],
                     'required': True, 'existing_snapshot_is_not_a_substitute': True},
        'restore_parameters': restore,
        'rds_configuration_reference': {k: db.get(k) for k in ('EngineVersion', 'StorageType', 'AllocatedStorage', 'BackupRetentionPeriod', 'PreferredBackupWindow', 'PreferredMaintenanceWindow', 'EnabledCloudwatchLogsExports', 'StorageEncrypted', 'KmsKeyId')},
        'actions_in_order': [
            'Create fresh manual RDS snapshot; wait and verify available, manual, correct source instance.',
            'Delete only the specified NAT gateway; wait until deleted.',
            'Verify EIP is unassociated, then release only the specified allocation.',
            'Reverify manual snapshot, then delete RDS (retain automated backups); wait until deleted.'],
        'preserved': 'All S3 buckets and contents, including Bronze; all resources except the three explicit targets.',
        'remaining_inventory_before_teardown': remaining, 'inventory_errors': errors,
        'scope_note': 'Regional inventory, not an account-wide billing audit. Inventory includes targets; subtract only the three targets after successful execution.',
        'ongoing_cost_categories': ['S3 storage/requests', 'Manual snapshots and retained automated backups', 'Secrets Manager storage/API calls', 'ECR image storage', 'CloudWatch logs storage/ingestion', 'Lambda/API Gateway usage', 'Any other public IPv4 allocations or active database resources'],
        'impact': 'RAG backend becomes unavailable. NAT routes are left in place and may become blackholes. Lambda, API Gateway, secrets, logs, networking, and images are not deleted.',
        'typed_confirmation': CONFIRM,
    }


def verify_snapshot(rds, snapshot):
    row = rds.describe_db_snapshots(DBSnapshotIdentifier=snapshot)['DBSnapshots'][0]
    if (row['DBSnapshotIdentifier'] != snapshot or row['DBInstanceIdentifier'] != DB
            or row['SnapshotType'] != 'manual' or row['Status'] != 'available'):
        raise RuntimeError('Fresh manual snapshot verification failed; stop without further changes')
    return row


def execute(c, plan, save):
    # No AWS mutation is allowed before this exact interactive confirmation.
    if input(f'Type exactly {CONFIRM}: ') != CONFIRM:
        raise RuntimeError('Confirmation mismatch; no AWS actions performed')
    snapshot = plan['snapshot']['identifier']
    c['rds'].create_db_snapshot(DBSnapshotIdentifier=snapshot, DBInstanceIdentifier=DB)
    c['rds'].get_waiter('db_snapshot_available').wait(DBSnapshotIdentifier=snapshot, WaiterConfig={'Delay':30,'MaxAttempts':120})
    verify_snapshot(c['rds'], snapshot)
    plan['snapshot_verified'] = True
    save()
    c['ec2'].delete_nat_gateway(NatGatewayId=NAT)
    c['ec2'].get_waiter('nat_gateway_deleted').wait(NatGatewayIds=[NAT], WaiterConfig={'Delay':15,'MaxAttempts':120})
    address = c['ec2'].describe_addresses(AllocationIds=[EIP])['Addresses'][0]
    if address.get('AssociationId'):
        raise RuntimeError('EIP is still associated; refusing to release')
    c['ec2'].release_address(AllocationId=EIP)
    verify_snapshot(c['rds'], snapshot)
    c['rds'].delete_db_instance(DBInstanceIdentifier=DB, SkipFinalSnapshot=True, DeleteAutomatedBackups=False)
    c['rds'].get_waiter('db_instance_deleted').wait(DBInstanceIdentifier=DB, WaiterConfig={'Delay':30,'MaxAttempts':120})
    plan['status'] = 'teardown_complete'
    save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='Read-only plan (default)')
    mode.add_argument('--execute', action='store_true')
    parser.add_argument('--expected-account', help='Required for execution; must match STS caller account')
    parser.add_argument('--output', type=Path, required=True, help='New private local plan/receipt file')
    args = parser.parse_args()
    if args.output.exists(): parser.error('Output exists; use a new filename')
    if args.execute and not args.expected_account: parser.error('--expected-account is required for execution')
    c = clients()
    plan = inventory(c)
    if args.expected_account and plan['account'] != args.expected_account: raise RuntimeError('AWS account mismatch')
    plan['status'] = 'dry_run_only' if not args.execute else 'prepared'
    with args.output.open('x', encoding='utf-8') as f: json.dump(plan,f,indent=2,default=str)
    def save(): args.output.write_text(json.dumps(plan,indent=2,default=str)+'\n',encoding='utf-8')
    print(json.dumps(plan,indent=2,default=str),flush=True)
    if args.execute:
        if plan['inventory_errors']: raise RuntimeError('Incomplete inventory; refusing execution')
        try: execute(c,plan,save)
        except Exception:
            plan['status']='failed_or_partial_review_before_retry';save();raise

if __name__ == '__main__': main()

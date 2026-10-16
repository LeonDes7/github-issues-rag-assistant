"""Preview an RDS snapshot restore; no NAT, EIP, Lambda, or secret changes."""
import argparse
import json
from pathlib import Path
import boto3
from botocore.config import Config
from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='Read-only restore plan (default)')
    mode.add_argument('--execute', action='store_true')
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--expected-account', required=True)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
    if receipt['region'] != 'us-east-2' or receipt['targets']['rds'] != 'github-rag-db':
        raise RuntimeError('Receipt target mismatch')
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    session = boto3.Session(region_name='us-east-2')
    config = Config(retries={'max_attempts':0},connect_timeout=10,read_timeout=30)
    sts = session.client('sts',config=config)
    if sts.get_caller_identity()['Account'] != args.expected_account or receipt['account'] != args.expected_account:
        raise RuntimeError('AWS account mismatch')
    rds = session.client('rds',config=config)
    snapshot = receipt['snapshot']['identifier']
    row = rds.describe_db_snapshots(DBSnapshotIdentifier=snapshot)['DBSnapshots'][0]
    if row['Status'] != 'available' or row['SnapshotType'] != 'manual' or row['DBInstanceIdentifier'] != 'github-rag-db':
        raise RuntimeError('Required manual snapshot is not available')
    # Refuse to overwrite an existing instance. Only the explicit not-found error is acceptable.
    try:
        rds.describe_db_instances(DBInstanceIdentifier='github-rag-db')
    except rds.exceptions.DBInstanceNotFoundFault:
        pass
    else:
        raise RuntimeError('Database already exists; refusing restore')
    params = dict(receipt['restore_parameters'])
    if params.get('DBInstanceIdentifier') != 'github-rag-db': raise RuntimeError('Restore identifier mismatch')
    params['DBSnapshotIdentifier'] = snapshot
    print(json.dumps({'mode':'execute' if args.execute else 'dry-run','restore_parameters':params,
        'unchanged':'S3 Bronze, NAT/EIP, Lambda, API Gateway, secrets, and security groups',
        'followup':'Review restored database configuration, backups, new endpoint, and replacement NAT/EIP/routes before separately approved Lambda/network/secret updates.',
        'typed_confirmation':'RESTORE github-rag-db'},indent=2))
    if not args.execute: return
    if input('Type exactly RESTORE github-rag-db: ') != 'RESTORE github-rag-db':
        raise RuntimeError('Confirmation mismatch; no AWS changes')
    rds.restore_db_instance_from_db_snapshot(**params)
    rds.get_waiter('db_instance_available').wait(DBInstanceIdentifier='github-rag-db',WaiterConfig={'Delay':30,'MaxAttempts':120})
    db = rds.describe_db_instances(DBInstanceIdentifier='github-rag-db')['DBInstances'][0]
    print(json.dumps({'status':db['DBInstanceStatus'],'new_endpoint':db['Endpoint'],
                      'warning':'Backend connectivity is not restored automatically.'},indent=2))

if __name__ == '__main__': main()

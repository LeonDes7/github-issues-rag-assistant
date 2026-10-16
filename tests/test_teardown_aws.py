"""Offline safety checks: these tests never use AWS credentials or network."""
import unittest
from unittest.mock import MagicMock, patch
from scripts import teardown_aws

class TeardownSafetyTests(unittest.TestCase):
    def plan(self):
        return {'snapshot':{'identifier':'fresh-manual'},'status':'prepared'}

    def test_wrong_confirmation_makes_no_aws_calls(self):
        clients={'rds':MagicMock(),'ec2':MagicMock()}
        with patch('builtins.input',return_value='yes'),self.assertRaises(RuntimeError):
            teardown_aws.execute(clients,self.plan(),lambda:None)
        self.assertEqual(clients['rds'].mock_calls,[])
        self.assertEqual(clients['ec2'].mock_calls,[])

    def test_snapshot_failure_prevents_deletion(self):
        clients={'rds':MagicMock(),'ec2':MagicMock()}
        clients['rds'].get_waiter.return_value.wait.side_effect=RuntimeError('snapshot failed')
        with patch('builtins.input',return_value=teardown_aws.CONFIRM),self.assertRaises(RuntimeError):
            teardown_aws.execute(clients,self.plan(),lambda:None)
        clients['ec2'].delete_nat_gateway.assert_not_called()
        clients['rds'].delete_db_instance.assert_not_called()

    def test_order_and_exact_scope(self):
        calls=MagicMock();rds=calls.rds;ec2=calls.ec2
        rds.describe_db_snapshots.return_value={'DBSnapshots':[{'DBSnapshotIdentifier':'fresh-manual','DBInstanceIdentifier':teardown_aws.DB,'SnapshotType':'manual','Status':'available'}]}
        ec2.describe_addresses.return_value={'Addresses':[{'AllocationId':teardown_aws.EIP}]}
        with patch('builtins.input',return_value=teardown_aws.CONFIRM):
            teardown_aws.execute({'rds':rds,'ec2':ec2},self.plan(),lambda:None)
        names=['call.'+c[0] for c in calls.mock_calls]
        self.assertLess(names.index('call.rds.describe_db_snapshots'),names.index('call.ec2.delete_nat_gateway'))
        self.assertLess(names.index('call.ec2.get_waiter().wait'),names.index('call.ec2.release_address'))
        self.assertLess(names.index('call.ec2.release_address'),names.index('call.rds.delete_db_instance'))
        ec2.delete_nat_gateway.assert_called_once_with(NatGatewayId=teardown_aws.NAT)
        ec2.release_address.assert_called_once_with(AllocationId=teardown_aws.EIP)
        rds.delete_db_instance.assert_called_once_with(DBInstanceIdentifier=teardown_aws.DB,SkipFinalSnapshot=True,DeleteAutomatedBackups=False)

    def test_default_preview_never_calls_execute(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory,patch('sys.argv',['teardown','--output',str(Path(directory)/'plan.json')]),patch.object(teardown_aws,'clients'),patch.object(teardown_aws,'inventory',return_value={'account':'test'}),patch.object(teardown_aws,'execute') as execute,patch('builtins.print'):
            teardown_aws.main()
            execute.assert_not_called()

    def test_wrong_snapshot_source_prevents_deletion(self):
        clients={'rds':MagicMock(),'ec2':MagicMock()}
        clients['rds'].describe_db_snapshots.return_value={'DBSnapshots':[{'DBSnapshotIdentifier':'fresh-manual','DBInstanceIdentifier':'other-db','SnapshotType':'manual','Status':'available'}]}
        with patch('builtins.input',return_value=teardown_aws.CONFIRM),self.assertRaises(RuntimeError):
            teardown_aws.execute(clients,self.plan(),lambda:None)
        clients['ec2'].delete_nat_gateway.assert_not_called()
        clients['rds'].delete_db_instance.assert_not_called()

    def test_associated_eip_is_not_released(self):
        clients={'rds':MagicMock(),'ec2':MagicMock()}
        clients['rds'].describe_db_snapshots.return_value={'DBSnapshots':[{'DBSnapshotIdentifier':'fresh-manual','DBInstanceIdentifier':teardown_aws.DB,'SnapshotType':'manual','Status':'available'}]}
        clients['ec2'].describe_addresses.return_value={'Addresses':[{'AssociationId':'still-attached'}]}
        with patch('builtins.input',return_value=teardown_aws.CONFIRM),self.assertRaises(RuntimeError):
            teardown_aws.execute(clients,self.plan(),lambda:None)
        clients['ec2'].release_address.assert_not_called()
        clients['rds'].delete_db_instance.assert_not_called()

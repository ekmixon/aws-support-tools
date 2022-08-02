#  Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
  
#  Licensed under the Apache License, Version 2.0 (the "License").
#  You may not use this file except in compliance with the License.
#  A copy of the License is located at
  
#      http://www.apache.org/licenses/LICENSE-2.0
  
#  or in the "license" file accompanying this file. This file is distributed 
#  on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either 
#  express or implied. See the License for the specific language governing 
#  permissions and limitations under the License.

#!/usr/bin/python
# run > python get_emr_cli_export.py j-2ABCABCABC
import boto3
import json
import sys

cluster_id = sys.argv[1]
client = boto3.client('emr')
clst = client.describe_cluster(ClusterId=cluster_id)
clst_info = clst['Cluster']

# non-list type
opt_keys = {
    '--release-label': 'ReleaseLabel',
    '--log-uri': 'LogUri',
    '--auto-terminate': 'AutoTerminate',
    '--auto-scaling-role': 'AutoScalingRole',
    '--ebs-root-volume-size': 'EbsRootVolumeSize',
    '--service-role': 'ServiceRole',
    '--name': 'Name',
}

awscli = "aws emr create-cluster "
for i, value in opt_keys.items():
    awscli += (
        f" {i}"
        if clst_info[value] is True
        else f" {i} {str(clst_info[opt_keys[i]])}"
    )

InstanceAtt = clst_info['Ec2InstanceAttributes']
cli_InstanceAtt = {'InstanceProfile': InstanceAtt.pop('IamInstanceProfile')}
cli_InstanceAtt['KeyName'] = InstanceAtt.pop('Ec2KeyName')
cli_InstanceAtt['SubnetId'] = InstanceAtt.pop('Ec2SubnetId')
cli_InstanceAtt['EmrManagedSlaveSecurityGroup'] = InstanceAtt.pop('EmrManagedSlaveSecurityGroup')
cli_InstanceAtt['EmrManagedMasterSecurityGroup'] = InstanceAtt.pop('EmrManagedMasterSecurityGroup')
awscli += ' --ec2-attributes ' + '\'' + str(json.dumps(cli_InstanceAtt)) + '\''


# list type
l_opt_keys = {'--applications': 'Applications', '--tags': 'Tags'}
awscli += ' --applications ' + " ".join(
    list(
        map(
            lambda a: f"Name={a['Name']}",
            clst_info[l_opt_keys['--applications']],
        )
    )
)

awscli += ' --tags ' + " ".join(list(map(lambda a: '\'%s=%s\'' % (a['Key'], a['Value']), clst_info[l_opt_keys['--tags']])))


# steps
cli_steps = []
steps = client.list_steps(ClusterId=cluster_id)
for item in steps['Steps']:
    cli_step = {
        'Name': item['Name'],
        'ActionOnFailure': item['ActionOnFailure'],
        'Args': item['Config']['Args'],
        'Jar': item['Config']['Jar'],
    }

    cli_steps.append(cli_step)

awscli += ' --steps ' + '\'' + json.dumps(cli_steps) + '\''

# instance groups
cli_igroups = []
igroups = client.list_instance_groups(ClusterId=cluster_id)
for item in igroups['InstanceGroups']:
    cli_igroup = {
        'InstanceCount': item['RequestedInstanceCount'],
        'InstanceGroupType': item['InstanceGroupType'],
        'InstanceType': item['InstanceType'],
        'Name': item['Name'],
    }

    if 'BidPrice' in item:
        cli_igroup['BidPrice'] = item['BidPrice']
    if len(item['EbsBlockDevices']) > 0:
        cli_igroup['EbsConfiguration'] = {'EbsBlockDeviceConfigs': {}}
        cli_igroup['EbsConfiguration']['EbsBlockDeviceConfigs']['VolumeSpecification'] = \
            list(map(lambda a: a['VolumeSpecification'], item['EbsBlockDevices']))
    cli_igroups.append(cli_igroup)

awscli += ' --instance-groups ' + '\'' + json.dumps(cli_igroups) + '\''
print(awscli)

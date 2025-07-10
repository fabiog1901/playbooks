# CockroachDB Collection

The Collection groups together Ansible Playbooks for deploying a CockroachDB Self Hosted cluster.

## Generate CA key pair

You can use playbook `generate_ca_certs.yaml` to create the required custom CA crt and key.
As writing at path `/var/lib/ca` requires privilege permisison, enter your MacOS password when prompted.

```bash
$ ansible-playbook playbooks/generate_ca_certs.yaml --ask-become-pass
BECOME password: <enter your MacOS login password>

PLAY [GENERATE CA CERTS] ********************

TASK [clean up directory] ********************
changed: [localhost]

TASK [create ca.key] ********************
changed: [localhost]

TASK [Create ca.cnf] ********************
changed: [localhost]

TASK [create the ca.crt] ********************
changed: [localhost]

TASK [Recreate index and serial files] ********************
changed: [localhost]

PLAY RECAP ********************
localhost                  : ok=5    changed=5    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0   
```

Verify the CA crt and key have been created.

```bash
$ ls -l /var/lib/ca/
total 40
-rw-r--r--  1 root  wheel   976B Jul 10 10:34 ca.cnf
-rw-r--r--  1 root  wheel   1.1K Jul 10 10:34 ca.crt
-r--------  1 root  wheel   1.7K Jul 10 10:34 ca.key
-rw-r--r--  1 root  wheel     1B Jul 10 10:34 index.txt
-rw-r--r--  1 root  wheel     3B Jul 10 10:34 serial.txt
```

You can now create your cluster.

## Setting up AWS, GCP, Azure credentials

The `create_cluster.yaml` playbook uses [`cloud_instance`](https://github.com/fabiog1901/cloud_instance) to provision VMs on the public cloud.

Install it

```bash
pip3 install cloud_instance
```

`cloud_instance` uses the public clouds native SDK methods for Authentication.

For example, for AWS you will have to issue command `aws sso login` to get updated credential files in `~/.aws/sso`.

GCP and AZURE will look for env variables, such as

```bash
GCP_SERVICE_ACCOUNT_FILE=/Users/fabio/cea-team.json
GCP_AUTH_KIND=serviceaccount
GCP_PROJECT=cea-team
```

Validate that authentication is working by issuing a command to fetch instances for a fake `deployment_id`

```bash
$ cloud_instance fake_deployment_id present '{}' '[]'
[]
```

As it returns an empty list `[]` without throwing any error, we know Authentication is correctly setup.

## Create a cluster

The playbook assumes you have CA certificate files in `/var/lib/ca/`, as discussed in a previous section.

File `deployments/sample.yaml` contains the details of the deployment

```bash
ansible-playbook playbooks/create_cluster.yaml  -e @deployments/sample.yaml
```

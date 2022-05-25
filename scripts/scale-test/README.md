# Scale testing

The aim of the scale testing benchmark is to establish a way to test, measure and validate the improvements implemented on microk8s.

Moreover this evaluation at scale can be used to communicate the exact performance achieved to customers and interested partners.

## Running the benchmark

### 1. vSphere setup

Currently, we are running it in vSphere/Boston cluster. You will need credentials to access it. Simply run:

```bash
./scripts/setup-vsphere.sh
```

and it will bootstrap a juju controller on a vSphere cloud, ready to deploy any charm!

You can specify `VS_USER`, `VS_PASS` and `VS_CONTROLLER` environment variables for a non-interactive install:

```bash
VS_USER="foo" VS_PASS="bar" VS_CONTROLLER="mycontroller" ./scripts/setup-vsphere.sh 
```

### 2. Microk8s cluster

Once the vSphere controller has been setup, you can use the `setup_cluster.py` script to create a Microk8s cluster on a new juju model. By default, it will create a single-node cluster on the `microk8s` namespace. However:

```bash
python scripts/scale-test/setup_cluster.py -m "mycluster" --nodes 10 --control-plane 3
```

will create a new juju model named `mycluster`, spin up 10 ubuntu instances on it and install `microk8s`. After that, it will join nodes as workers or not depending on the number of control-plane nodes were specified.

Check out `python setup_cluster.py -h` for more detailed instructions on how to use the tool.
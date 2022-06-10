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
Once a juju controller has been setup, you can use the `setup_cluster.py` script to create a Microk8s cluster on a new juju model. By default, it will create a single-node cluster on the `microk8s` namespace. However:

```bash
python scripts/scale-test/setup_cluster.py -m "mycluster" --nodes 10 --control-plane 3
```

will create a new juju model named `mycluster`, spin up 10 ubuntu instances on it and install `microk8s`. After that, it will join nodes as workers or not depending on the number of control-plane nodes were specified. You can also specify which channel you want to install by using the `--channel` argument.

Check out `python setup_cluster.py --help` for more detailed instructions on how to use the tool.

Note that a `<model>_cluster.json` file will be created with some information about the cluster at hand. This is later needed to run experiments.

#### Docker credentials
If you are trying to setup a large cluster, you will most probably hit dockerhub rate-limit errors (see [this documentation page](https://microk8s.io/docs/dockerhub-limits)).

To workaround this, you can specify the docker login credentials with

```bash
python setup_cluter.py --docker-username foo --docker-password bar
```

or with env variables

```bash
export DOCKER_USERNAME="foo"
export DOCKER_PASSWORD="bar"
python setup_cluter.py
```

and containerd on all nodes will be configured accordingly.

#### HTTP proxy settings
If you are running this script on a network-restricted environment (like vSphere cluster), you may need to specify the http proxy to configure the nodes. You can do so with the `--http-proxy` argument:

```bash
python setup_cluster.py --http-proxy http://squid.internal:3128
```

### 3. Running the experiment
The experiment consists on deploying some workloads (yaml files) on a temporary namespace during some time. Some measurements are done on nodes, like cpu and memory usage of dqlite processes on control plane nodes. The resulting metric csv files will be stored under `data/scale-test/run_{date}/`.

To run an experiment on a specific cluster, just do:
```bash
PYTHONPATH=$PYTHONPATH:. python scale_test/experiment.py -c mycluster_cluster.json
```
Where `mycluster_cluster.json` is the file output from the `setup_cluster.py` step.  
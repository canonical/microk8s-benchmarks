# Scale testing

The aim of the scale testing benchmark is to establish a way to test, measure and validate the improvements implemented on microk8s.

Moreover this evaluation at scale can be used to communicate the exact performance achieved to customers and interested partners.

## Running the benchmark

### vSphere setup

Currently, we are running it in vSphere/Boston cluster. You will need credentials to access it. Simply run:

```bash
./scripts/setup-vsphere.sh
```

and it will bootstrap a juju controller on a vSphere cloud, ready to deploy any charm!

You can specify `VS_USER`, `VS_PASS` and `VS_CONTROLLER` environment variables for a non-interactive install:

```bash
VS_USER="foo" VS_PASS="bar" VS_CONTROLLER="mycontroller" ./scripts/setup-vsphere.sh 
```
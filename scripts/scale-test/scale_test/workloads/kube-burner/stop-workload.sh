#!/bin/bash

kill -9 $(pgrep kube-burner) || true

kube-burner destroy --uuid foobar
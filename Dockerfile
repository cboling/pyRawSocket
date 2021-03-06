# Copyright 2020, Boling Consulting Solutions
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM python:3.6.9-slim-buster

MAINTAINER Chip Boling <chip@bcsw.net>

# Update to have latest images
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python python-pip gcc build-essential python-dev libpcap-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

# Load all dependencies for testing
RUN mkdir -p /tmp/test
COPY requirements.txt /tmp
COPY test/requirements.txt /tmp/test

RUN pip install --no-cache-dir -r /tmp/test/requirements.txt
RUN pip install pydevd-pycharm~=201.7846.77
RUN pip install twisted
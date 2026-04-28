PYTHON ?= python3
PYCACHE ?= /tmp/law-crawler-pycache

.PHONY: test compile check

test:
	PYTHONPYCACHEPREFIX=$(PYCACHE) $(PYTHON) -m unittest discover tests/unit

compile:
	PYTHONPYCACHEPREFIX=$(PYCACHE) $(PYTHON) -m compileall main.py src tests/unit

check: test compile


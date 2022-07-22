pip-compile:
	pip-compile requirements.in > requirements.txt

pip-compile-dev:
	pip-compile requirements-dev.in > requirements-dev.txt

pip-compile-all: pip-compile pip-compile-dev

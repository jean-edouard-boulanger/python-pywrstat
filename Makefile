pip-compile:
	pip-compile requirements.in > requirements.txt

pip-compile-dev:
	pip-compile requirements-dev.in > requirements-dev.txt

pip-compile-all: pip-compile pip-compile-dev

lint:
	isort . && black .

sphinx-build:
	sphinx-build -b html docs/source/ docs/build/html

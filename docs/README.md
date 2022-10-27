Install requirements for documentation:

```bash
pip install -r docs/requirements.txt
```

Use `sphinx-autobuild` to watch and build docs during development:

```bash
sphinx-autobuild docs/source docs/build/html --watch $(GIT_ROOT)/prometheus_client
```

# Contributing

Prometheus uses GitHub to manage reviews of pull requests.

* If you have a trivial fix or improvement, go ahead and create a pull request,
  addressing (with `@...`) the maintainer of this repository (see
  [MAINTAINERS.md](MAINTAINERS.md)) in the description of the pull request.

* If you plan to do something more involved, first discuss your ideas on
  [our mailing list]. This will avoid unnecessary work and surely give you and
  us a good deal of inspiration.

* Before your contributions can be landed, they must be signed off under the
  [Developer Certificate of Origin] which asserts you own and have the right to
  submit the change under the open source licence used by the project.

## Testing

Submitted changes should pass the current tests, and be covered by new test
cases when adding functionality.

* [Install `pre-commit`](https://pre-commit.com/index.html#installation)
  and run `pre-commit install` in the repository.

* Run the tests locally using [tox] which executes the full suite on all
  supported Python versions installed.

* Each pull request is gated using [CircleCI] with the results linked on the
  GitHub page. This must pass before the change can land, note pushing a new
  change will trigger a retest.

## Style

* Code style should follow [PEP 8] generally, and can be checked by running:
  `pre-commit run`.


[our mailing list]: https://groups.google.com/forum/?fromgroups#!forum/prometheus-developers
[Developer Certificate of Origin]: https://github.com/prometheus/prometheus/wiki/DCO-signing
[isort]: https://pypi.org/project/isort/
[PEP 8]: https://www.python.org/dev/peps/pep-0008/
[tox]: https://tox.readthedocs.io/en/latest/
[CircleCI]: https://circleci.com/

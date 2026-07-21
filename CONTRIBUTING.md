# Contributing

Thanks for your interest in improving the Wherobots QGIS plugin. This is a
[Wherobots Labs](https://wherobots.com/labs) project: experimental,
community-friendly, and maintained on a best-effort basis by its authoring
team rather than under a production SLA.

## Support expectations

- **Functional issues** are addressed opportunistically, with no guaranteed
  response time. [GitHub Issues](https://github.com/wherobots/labs-wherobots_qgis/issues)
  is the only public support channel.
- **Security issues** are the exception and are handled on a timely basis under
  Wherobots' standard security policy. Please report suspected vulnerabilities
  privately (see [Reporting security issues](#reporting-security-issues)) rather
  than opening a public issue.

## How to contribute

1. Open an issue describing the bug or proposed change before large work, so we
   can confirm it fits the plugin's scope.
2. Fork the repo and create a topic branch.
3. Make your change with tests (see below) and a clear description.
4. Open a pull request. Contributing grants no access to core Wherobots repos;
   this repo manages its own collaborators.

## Development and tests

The plugin's pure-Python logic is unit-tested outside QGIS — the suite stubs
the `qgis`/`PyQt` runtime, so no QGIS install is required to run it:

```bash
pip install -r requirements-dev.txt
pytest
```

Automated tests must pass in CI before a PR can merge. New behavior should come
with tests. The plugin is written to run on both QGIS 3.x (Qt5) and QGIS 4.0
(Qt6) from one codebase — see [`docs/qgis4-compat.md`](docs/qgis4-compat.md)
before touching Qt imports or enums.

## Release gates

Because this is a Labs project, every public release must clear three gates:

1. **Design review** — human sign-off of the high-level design.
2. **Security review** — human review of secrets, credentials, dependency risk,
   and internal-infra exposure, signed off by the Wherobots security team.
3. **Automated tests** — CI is green.

## Reporting security issues

Do not open a public issue for security vulnerabilities. Report them to the
Wherobots security team following Wherobots' standard security policy so they
can be triaged and fixed under that process.

## License

By contributing, you agree that your contributions are licensed under the
project's [Apache License 2.0](LICENSE).

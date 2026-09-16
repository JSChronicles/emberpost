from importlib.metadata import PackageNotFoundError

import pytest

from emberpost.cli import _package_version, main


def test_cli_version_prints_installed_package_version(monkeypatch, capsys) -> None:
    monkeypatch.setattr("emberpost.cli._package_version", lambda _: "1.2.3")
    monkeypatch.setattr("sys.argv", ["emberpost", "--version"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert capsys.readouterr().out == "emberpost 1.2.3\n"


def test_package_version_falls_back_when_distribution_is_missing(monkeypatch) -> None:
    def raise_not_found(_: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr("emberpost.cli.importlib_metadata.version", raise_not_found)

    assert _package_version("missing") == "unknown"

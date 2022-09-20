"""Nox configuration to Lint, Format, and Test code."""
import nox


@nox.session(reuse_venv=True)
def reformat(session: nox.Session) -> None:
    """Reformat using Black."""
    session.install("black")
    session.run("black", ".")


@nox.session(reuse_venv=True)
def lint(session: nox.Session) -> None:
    """Lint using Flake8."""
    session.install(
        "flake8",
        "flake8-docstrings",
        "flake8-import-order",
        "nox",
    )

    session.run("flake8", "--max-complexity=8")


@nox.session(reuse_venv=True)
def test(session: nox.Session) -> None:
    """Run unit tests using Pytest Coverage."""
    session.install(
        "pytest",
        "pytest-cov",
        "pytest-asyncio",
    )

    session.run("pytest")

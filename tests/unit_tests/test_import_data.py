"""``import_()`` will not import a file's name as if it were SurrealQL."""

from pathlib import Path

import pytest

from surrealdb.connections.import_export import aimport_sql, import_sql
from surrealdb.connections.url import Url

# Never reached: the import is refused before any request is made.
UNREACHABLE = Url("http://127.0.0.1:9")


@pytest.fixture
def backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "backup.surql"
    path.write_text("OPTION IMPORT;\nCREATE person:one;\n")
    return path


def test_a_str_naming_a_file_is_refused(backup: Path) -> None:
    with pytest.raises(ValueError, match=r"pathlib\.Path\('backup\.surql'\)"):
        import_sql(UNREACHABLE, "backup.surql", 1, None, None, None)


async def test_an_async_str_naming_a_file_is_refused(backup: Path) -> None:
    with pytest.raises(ValueError, match="is the name of a file"):
        await aimport_sql(UNREACHABLE, str(backup), 1, None, None, None)

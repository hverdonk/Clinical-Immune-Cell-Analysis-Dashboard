import sqlite3
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis-dashboard"))

import load_cell_counts as lcc


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    """Write a minimal CSV file for ingestion tests.

    This helper constructs a CSV from an explicit header row and a list of raw
    string rows, writing it to `path`.
    """
    content_lines = [",".join(header)]
    content_lines.extend(",".join(row) for row in rows)
    path.write_text("\n".join(content_lines) + "\n")


def test_load_csv_into_db_success(tmp_path: Path) -> None:
    """`load_csv_into_db` loads one CSV row into SQLite with correct relational data.

    Validates that:
    - project/subject/sample rows are inserted with the expected values
    - one `sample_cell_count` row exists per population
    - the sum of inserted counts matches the input
    """
    csv_path = tmp_path / "cell-count.csv"
    db_path = tmp_path / "cell_counts.sqlite"

    header = [
        "project",
        "subject",
        "condition",
        "age",
        "sex",
        "treatment",
        "response",
        "sample",
        "sample_type",
        "time_from_treatment_start",
        *lcc.CELL_POPULATIONS,
    ]

    rows = [
        [
            "Proj1",
            "S01",
            "Healthy",
            "34",
            "F",
            "DrugA",
            "Responder",
            "S01_T0",
            "PBMC",
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
        ]
    ]

    _write_csv(csv_path, header, rows)

    lcc.load_csv_into_db(csv_path=csv_path, db_path=db_path)

    conn = sqlite3.connect(db_path)
    try:
        project = conn.execute("SELECT id, name FROM project").fetchall()
        assert len(project) == 1
        assert project[0][1] == "Proj1"

        subject = conn.execute(
            "SELECT subject_code, condition, age, sex FROM subject"
        ).fetchall()
        assert len(subject) == 1
        assert subject[0] == ("S01", "Healthy", 34, "F")

        sample = conn.execute(
            "SELECT sample_code, sample_type, time_from_treatment_start, treatment, response FROM sample"
        ).fetchall()
        assert len(sample) == 1
        assert sample[0] == ("S01_T0", "PBMC", 0, "DrugA", "Responder")

        counts = conn.execute(
            """
            SELECT COUNT(*)
            FROM sample_cell_count
            """
        ).fetchone()[0]
        assert counts == len(lcc.CELL_POPULATIONS)

        total = conn.execute(
            """
            SELECT SUM(count)
            FROM sample_cell_count
            """
        ).fetchone()[0]
        assert total == 15

    finally:
        conn.close()


def test_load_csv_into_db_missing_file(tmp_path: Path) -> None:
    """`load_csv_into_db` raises `FileNotFoundError` when the input CSV path is missing."""
    csv_path = tmp_path / "does_not_exist.csv"
    db_path = tmp_path / "cell_counts.sqlite"

    with pytest.raises(FileNotFoundError):
        lcc.load_csv_into_db(csv_path=csv_path, db_path=db_path)


def test_load_csv_into_db_missing_required_column(tmp_path: Path) -> None:
    """`load_csv_into_db` rejects CSVs missing required columns.

    Specifically verifies that omitting `time_from_treatment_start` causes a
    `ValueError` with an informative message.
    """
    csv_path = tmp_path / "cell-count.csv"
    db_path = tmp_path / "cell_counts.sqlite"

    header = [
        "project",
        "subject",
        "condition",
        "age",
        "sex",
        "treatment",
        "response",
        "sample",
        "sample_type",
        # missing "time_from_treatment_start"
        *lcc.CELL_POPULATIONS,
    ]

    rows = [
        [
            "Proj1",
            "S01",
            "Healthy",
            "",
            "",
            "",
            "",
            "S01_T0",
            "",
            "1",
            "2",
            "3",
            "4",
            "5",
        ]
    ]

    _write_csv(csv_path, header, rows)

    with pytest.raises(ValueError, match=r"CSV missing required columns"):
        lcc.load_csv_into_db(csv_path=csv_path, db_path=db_path)


def test_load_csv_into_db_missing_population_count_raises(tmp_path: Path) -> None:
    """`load_csv_into_db` raises a ValueError when a required population count cell is empty."""
    csv_path = tmp_path / "cell-count.csv"
    db_path = tmp_path / "cell_counts.sqlite"

    header = [
        "project",
        "subject",
        "condition",
        "age",
        "sex",
        "treatment",
        "response",
        "sample",
        "sample_type",
        "time_from_treatment_start",
        *lcc.CELL_POPULATIONS,
    ]

    # Leave the last population blank
    rows = [
        [
            "Proj1",
            "S01",
            "Healthy",
            "",
            "",
            "",
            "",
            "S01_T0",
            "",
            "",
            "1",
            "2",
            "3",
            "4",
            "",
        ]
    ]

    _write_csv(csv_path, header, rows)

    with pytest.raises(ValueError, match=r"Missing count for population="):
        lcc.load_csv_into_db(csv_path=csv_path, db_path=db_path)

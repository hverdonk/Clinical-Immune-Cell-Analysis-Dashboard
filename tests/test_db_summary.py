import sqlite3
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis-dashboard"))

import load_cell_counts as lcc
import db_summary as db


def _setup_db(db_path: Path) -> None:
    """Create an empty SQLite database with the application schema.

    This helper initializes all tables/indexes via `lcc.SCHEMA_SQL` and inserts the
    canonical set of immune cell populations so downstream tests can insert sample
    counts and run the dashboard summary query.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(lcc.SCHEMA_SQL)
        conn.executemany(
            "INSERT OR IGNORE INTO cell_population(name) VALUES (?)",
            [(p,) for p in lcc.CELL_POPULATIONS],
        )
        conn.commit()
    finally:
        conn.close()


def _insert_sample_with_counts(
    db_path: Path,
    *,
    sample_code: str,
    counts_by_population: dict[str, int],
) -> None:
    """Insert one sample and per-population counts into the SQLite database.

    This helper creates minimal project/subject/sample rows of test data required by
    foreign keys, then inserts (or replaces) `sample_cell_count` records for the
    provided `counts_by_population` mapping.
    """
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute("INSERT OR IGNORE INTO project(name) VALUES (?)", ("Proj",))
            project_id = conn.execute(
                "SELECT id FROM project WHERE name = ?", ("Proj",)
            ).fetchone()[0]

            conn.execute(
                """
                INSERT OR IGNORE INTO subject(project_id, subject_code, condition, age, sex)
                VALUES (?, ?, ?, ?, ?)
                """,
                (project_id, "S01", "Healthy", 34, "F"),
            )
            subject_id = conn.execute(
                "SELECT id FROM subject WHERE project_id = ? AND subject_code = ?",
                (project_id, "S01"),
            ).fetchone()[0]

            conn.execute(
                """
                INSERT OR REPLACE INTO sample(
                    subject_id, sample_code, sample_type, time_from_treatment_start, treatment, response
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (subject_id, sample_code, "PBMC", 0, "DrugA", "Responder"),
            )
            sample_id = conn.execute(
                "SELECT id FROM sample WHERE sample_code = ?", (sample_code,)
            ).fetchone()[0]

            for pop, count in counts_by_population.items():
                pop_id = conn.execute(
                    "SELECT id FROM cell_population WHERE name = ?", (pop,)
                ).fetchone()[0]
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sample_cell_count(sample_id, population_id, count)
                    VALUES (?, ?, ?)
                    """,
                    (sample_id, pop_id, int(count)),
                )
    finally:
        conn.close()


def test_load_summary_with_sample_metadata_from_db_returns_expected_shape_and_columns(tmp_path: Path) -> None:
    """`load_summary_with_sample_metadata_from_db` returns a long-format summary with the expected schema.

    Verifies that the returned DataFrame has the exact expected columns and one row
    per population for the inserted sample.
    """
    db_path = tmp_path / "cell_counts.sqlite"
    _setup_db(db_path)

    counts = {p: i + 1 for i, p in enumerate(lcc.CELL_POPULATIONS)}
    _insert_sample_with_counts(db_path, sample_code="S01_T0", counts_by_population=counts)

    df = db.load_summary_with_sample_metadata_from_db(db_path)

    assert list(df.columns) == [
        "sample",
        "sample_type",
        "treatment",
        "response",
        "total_count",
        "population",
        "count",
        "percentage",
    ]
    assert len(df) == len(lcc.CELL_POPULATIONS)
    assert set(df["population"].tolist()) == set(lcc.CELL_POPULATIONS)


def test_load_summary_with_sample_metadata_from_db_totals_and_percentages(tmp_path: Path) -> None:
    """`load_summary_with_sample_metadata_from_db` computes correct totals and relative frequencies.

    Checks that `total_count` equals the sum of counts across all populations and
    that `percentage` is computed as `count / total_count * 100`.
    """
    db_path = tmp_path / "cell_counts.sqlite"
    _setup_db(db_path)

    counts = {
        "b_cell": 10,
        "cd8_t_cell": 20,
        "cd4_t_cell": 30,
        "nk_cell": 40,
        "monocyte": 50,
    }
    _insert_sample_with_counts(db_path, sample_code="S01_T0", counts_by_population=counts)

    df = db.load_summary_with_sample_metadata_from_db(db_path)

    total_expected = sum(counts.values())
    assert (df["total_count"] == total_expected).all()

    for _, row in df.iterrows():
        pop = row["population"]
        assert row["count"] == counts[pop]
        assert row["percentage"] == pytest.approx(counts[pop] * 100.0 / total_expected)


def test_load_summary_with_sample_metadata_from_db_missing_file_raises(tmp_path: Path) -> None:
    """`load_summary_with_sample_metadata_from_db` fails fast when the database file does not exist."""
    db_path = tmp_path / "does_not_exist.sqlite"

    with pytest.raises(FileNotFoundError):
        db.load_summary_with_sample_metadata_from_db(db_path)

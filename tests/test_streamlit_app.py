import sqlite3
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis-dashboard"))

import load_cell_counts as lcc
import streamlit_app as app

# TODO: add per-function docstrings with description of what's being tested
def _setup_db(db_path: Path) -> None:
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


def test_load_summary_from_db_returns_expected_shape_and_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "cell_counts.sqlite"
    _setup_db(db_path)

    counts = {p: i + 1 for i, p in enumerate(lcc.CELL_POPULATIONS)}
    _insert_sample_with_counts(db_path, sample_code="S01_T0", counts_by_population=counts)

    df = app.load_summary_from_db(db_path)

    assert list(df.columns) == [
        "sample",
        "total_count",
        "population",
        "count",
        "percentage",
    ]
    assert len(df) == len(lcc.CELL_POPULATIONS)
    assert set(df["population"].tolist()) == set(lcc.CELL_POPULATIONS)


def test_load_summary_from_db_totals_and_percentages(tmp_path: Path) -> None:
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

    df = app.load_summary_from_db(db_path)

    total_expected = sum(counts.values())
    assert (df["total_count"] == total_expected).all()

    for _, row in df.iterrows():
        pop = row["population"]
        assert row["count"] == counts[pop]
        assert row["percentage"] == pytest.approx(counts[pop] * 100.0 / total_expected)


def test_load_summary_from_db_missing_file_raises(tmp_path: Path) -> None:
    db_path = tmp_path / "does_not_exist.sqlite"

    with pytest.raises(FileNotFoundError):
        app.load_summary_from_db(db_path)

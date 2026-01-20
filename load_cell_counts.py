import csv
import sqlite3
from pathlib import Path
from typing import Dict, Optional, Tuple


CELL_POPULATIONS = [
    "b_cell",
    "cd8_t_cell",
    "cd4_t_cell",
    "nk_cell",
    "monocyte",
]


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS project (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS subject (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    subject_code TEXT NOT NULL,
    condition TEXT NOT NULL,
    age INTEGER,
    sex TEXT,
    UNIQUE(project_id, subject_code)
);

CREATE TABLE IF NOT EXISTS sample (
    id INTEGER PRIMARY KEY,
    subject_id INTEGER NOT NULL REFERENCES subject(id) ON DELETE CASCADE,
    sample_code TEXT NOT NULL UNIQUE,
    sample_type TEXT,
    time_from_treatment_start INTEGER,
    treatment TEXT,
    response TEXT
);

CREATE TABLE IF NOT EXISTS cell_population (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS sample_cell_count (
    sample_id INTEGER NOT NULL REFERENCES sample(id) ON DELETE CASCADE,
    population_id INTEGER NOT NULL REFERENCES cell_population(id) ON DELETE RESTRICT,
    count INTEGER NOT NULL,
    PRIMARY KEY (sample_id, population_id)
);

CREATE INDEX IF NOT EXISTS idx_subject_project_subject_code
    ON subject(project_id, subject_code);

CREATE INDEX IF NOT EXISTS idx_sample_subject_id
    ON sample(subject_id);

CREATE INDEX IF NOT EXISTS idx_sample_cell_count_population
    ON sample_cell_count(population_id);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.executemany(
        "INSERT OR IGNORE INTO cell_population(name) VALUES (?)",
        [(p,) for p in CELL_POPULATIONS],
    )


def _get_id_cached(
    conn: sqlite3.Connection,
    cache: Dict[Tuple[str, str], int],
    cache_key: Tuple[str, str],
    select_sql: str,
    select_params: Tuple[object, ...],
) -> int:
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    row = conn.execute(select_sql, select_params).fetchone()
    if row is None:
        raise RuntimeError(f"Expected row not found for key={cache_key}")

    _id = int(row[0])
    cache[cache_key] = _id
    return _id


def load_csv_into_db(csv_path: Path, db_path: Path) -> None:
    if not csv_path.exists():
        raise FileNotFoundError(str(csv_path))

    conn = connect(db_path)
    try:
        initialize_schema(conn)

        project_cache: Dict[Tuple[str, str], int] = {}
        subject_cache: Dict[Tuple[str, str], int] = {}
        population_cache: Dict[Tuple[str, str], int] = {}

        # Cache population IDs
        for p in CELL_POPULATIONS:
            pop_id = conn.execute(
                "SELECT id FROM cell_population WHERE name = ?",
                (p,),
            ).fetchone()[0]
            population_cache[("cell_population", p)] = int(pop_id)

        with csv_path.open("r", newline="") as f:
            reader = csv.DictReader(f)

            required = {
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
                *CELL_POPULATIONS,
            }
            if reader.fieldnames is None:
                raise ValueError("CSV file has no header")

            missing = required.difference(set(reader.fieldnames))
            if missing:
                raise ValueError(f"CSV missing required columns: {sorted(missing)}")

            with conn:
                for row in reader:
                    project_name = row["project"].strip()
                    subject_code = row["subject"].strip()

                    condition = row["condition"].strip()
                    age_str = row["age"].strip()
                    age: Optional[int] = int(age_str) if age_str != "" else None

                    sex = row["sex"].strip() or None
                    treatment = row["treatment"].strip() or None
                    response = row["response"].strip() or None

                    sample_code = row["sample"].strip()
                    sample_type = row["sample_type"].strip() or None

                    tfts_str = row["time_from_treatment_start"].strip()
                    time_from_treatment_start: Optional[int]
                    time_from_treatment_start = (
                        int(tfts_str) if tfts_str != "" else None
                    )

                    conn.execute(
                        "INSERT OR IGNORE INTO project(name) VALUES (?)",
                        (project_name,),
                    )
                    project_id = _get_id_cached(
                        conn,
                        project_cache,
                        ("project", project_name),
                        "SELECT id FROM project WHERE name = ?",
                        (project_name,),
                    )

                    conn.execute(
                        """
                        INSERT OR IGNORE INTO subject(
                            project_id, subject_code, condition, age, sex
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (project_id, subject_code, condition, age, sex),
                    )
                    subject_id = _get_id_cached(
                        conn,
                        subject_cache,
                        ("subject", f"{project_id}:{subject_code}"),
                        "SELECT id FROM subject WHERE project_id = ? AND subject_code = ?",
                        (project_id, subject_code),
                    )

                    conn.execute(
                        """
                        INSERT OR REPLACE INTO sample(
                            subject_id,
                            sample_code,
                            sample_type,
                            time_from_treatment_start,
                            treatment,
                            response
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            subject_id,
                            sample_code,
                            sample_type,
                            time_from_treatment_start,
                            treatment,
                            response,
                        ),
                    )

                    sample_id = conn.execute(
                        "SELECT id FROM sample WHERE sample_code = ?",
                        (sample_code,),
                    ).fetchone()[0]

                    counts_to_insert = []
                    for pop in CELL_POPULATIONS:
                        val = row[pop].strip()
                        if val == "":
                            raise ValueError(
                                f"Missing count for population={pop} sample={sample_code}"
                            )
                        count = int(val)
                        pop_id = population_cache[("cell_population", pop)]
                        counts_to_insert.append((int(sample_id), int(pop_id), count))

                    conn.executemany(
                        """
                        INSERT OR REPLACE INTO sample_cell_count(
                            sample_id, population_id, count
                        ) VALUES (?, ?, ?)
                        """,
                        counts_to_insert,
                    )

    finally:
        conn.close()


def main() -> None:
    base = Path(__file__).resolve().parent
    csv_path = base / "cell-count.csv"
    db_path = base / "cell_counts.sqlite"
    load_csv_into_db(csv_path=csv_path, db_path=db_path)


if __name__ == "__main__":
    main()

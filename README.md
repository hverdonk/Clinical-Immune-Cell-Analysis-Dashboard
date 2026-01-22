# Clinical Immune Cell Analysis Dashboard

Interactive Streamlit dashboard for exploring immune cell population relative frequencies across samples/projects, with responder vs non-responder comparisons and mixed-effects-model statistics.

## Dashboard

- **Live dashboard**: http://localhost:8501/ or `https://${CODESPACE_NAME}-8050.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}` when running in GitHub Codespaces. GitHub Codespaces will automatically forward port 8501 to your local machine and open the dashboard in your default browser.

## Quickstart (Local or GitHub Codespaces)

These steps reproduce the local database build and dashboard outputs using the committed example dataset in `analysis-dashboard/data/cell-count.csv`.

### 1) Start the dashboard (one command)

The dashboard should automatically install all dependencies and start the app. However, if you want to run it manually, use the following commands:

```bash
make run
```

This will:

- Install Python dependencies.
- Build `analysis-dashboard/cell_counts.sqlite` (if missing).
- Start Streamlit on port `8501`.

Open the forwarded port `8501` in Codespaces to view the app.

### Manual setup (without Makefile)

```bash
python -m pip install -r requirements.txt
python analysis-dashboard/load_cell_counts.py
streamlit run analysis-dashboard/streamlit_app.py --server.port 8501
```

### 2) Run tests

```bash
make test
```

### Troubleshooting

The dashboard should automatically install all dependencies, build the database, and start the dashboard. The entire process should take a few minutes. If you are having trouble running the dashboard in Codespaces, try the following:

- Disable adblockers and VPNs, use a private/incognito browser window, or configure your network to allow access to `localhost:8501`, especially if you are running the dashboard via the Codespaces web interface in your browser.
- Use the VSCode Codespaces plugin to connect to the Codespaces instance and run the dashboard.
- Try running the dashboard locally instead of via the Codespaces web interface.

## Data model / relational database schema

The application uses a small SQLite database designed around a normalized “project -> subject -> sample” hierarchy with a reference table for cell populations.

### Tables

#### `project`

- **Purpose**: top-level grouping (e.g., study, trial, cohort, analysis batch).
- **Columns**:
  - `id` (PK)
  - `name` (unique)

#### `subject`

- **Purpose**: patient/participant metadata scoped to a project.
- **Columns**:
  - `id` (PK)
  - `project_id` (FK -> `project.id`, `ON DELETE CASCADE`)
  - `subject_code` (project-scoped identifier)
  - `condition`, `age`, `sex`
- **Constraint**:
  - `UNIQUE(project_id, subject_code)` ensures no duplicate subject codes within a project.

#### `sample`

- **Purpose**: a biological sample or timepoint collected from a subject.
- **Columns**:
  - `id` (PK)
  - `subject_id` (FK -> `subject.id`, `ON DELETE CASCADE`)
  - `sample_code` (unique sample identifier)
  - `sample_type` (e.g., PBMC, TIL)
  - `time_from_treatment_start`
  - `treatment`
  - `response`

#### `cell_population`

- **Purpose**: reference / dimension table enumerating immune cell populations.
- **Columns**:
  - `id` (PK)
  - `name` (unique)

#### `sample_cell_count`

- **Purpose**: fact table storing the measured cell count for each `(sample, population)` pair.
- **Columns**:
  - `sample_id` (FK -> `sample.id`, `ON DELETE CASCADE`)
  - `population_id` (FK -> `cell_population.id`, `ON DELETE RESTRICT`)
  - `count` (integer)
- **Primary key**:
  - `PRIMARY KEY (sample_id, population_id)` ensures one row per population per sample.

### Indexes

The schema includes indexes that match common join/filter patterns in the dashboard query:

- `idx_subject_project_subject_code` on `(project_id, subject_code)`
- `idx_sample_subject_id` on `sample(subject_id)`
- `idx_sample_cell_count_population` on `sample_cell_count(population_id)`

### Why this schema?

- **Normalized entities**: projects, subjects, and samples are stored once, reducing duplication and enabling consistent metadata updates.
- **Star-like analytics shape**: `sample_cell_count` acts as a fact table; `project/subject/sample/cell_population` are dimension tables. This is a common pattern for analytics workloads and scales cleanly.
- **Efficient “long format” output**: the dashboard query produces one row per `(sample, population)` with computed totals and relative frequencies (proportion and percent). This is directly consumable for plotting and statistical modeling.

### How this scales (hundreds of projects, thousands of samples, more analytics)

SQLite is sufficient for the small demo dataset, but the relational design can be migrated directly to Postgres/MySQL for larger deployments.

If you scale up:

- **Partitioning / sharding** (in Postgres, etc.): partition `sample` or `sample_cell_count` by `project_id` and/or by time to keep queries fast.
- **Additional dimensions**:
  - Add `assay` / `modality` tables (flow, CyTOF, scRNA-seq derived abundances, etc.).
  - Add `analyte` tables for different feature types (gene, protein marker, cell state), keeping a consistent fact-table pattern.
- **Multiple metric types**:
  - Keep `sample_cell_count` for raw counts.
  - Add a `sample_cell_metric(sample_id, population_id, metric_name, value)` table if you want arbitrary derived metrics (percentages, QC metrics, scores) without changing schema.
- **Analytics results persistence**:
  - Add `analysis_run` (id, parameters JSON, timestamp, code version) and `analysis_result` tables to store outputs (effect sizes, p-values, model diagnostics) and make results reproducible and queryable.
- **Performance considerations**:
  - Materialize a per-sample totals table (or a view/materialized view) to avoid recomputing totals at query time for very large datasets.
  - Add composite indexes aligned to your most common filters (e.g., `sample(treatment, response, time_from_treatment_start)` in a server DB).

## Code structure (and design rationale)

The repository is organized around a simple pipeline:

- **`analysis-dashboard/load_cell_counts.py`**
  - Creates/initializes the SQLite schema (`SCHEMA_SQL`).
  - Loads `analysis-dashboard/data/cell-count.csv` into normalized tables.
  - Rationale: ingestion is isolated from the dashboard so you can swap data sources (CSV -> API -> LIMS export) without touching UI logic.

- **`analysis-dashboard/db_summary.py`**
  - Provides a single “authoritative” query function: `load_summary_with_sample_metadata_from_db`.
  - Returns a long-format DataFrame with metadata + raw counts + computed totals/proportions.
  - Rationale: one well-defined query boundary keeps the UI code simple and makes it easy to validate with unit tests.

- **`analysis-dashboard/response_plot.py`**
  - Contains reusable data transforms used by the dashboard:
    - `apply_filters` (multi-dimensional filtering)
    - `get_patient_count` (unique subject count at baseline)
    - `responder_boxplot_spec` (Vega-Lite spec for plotting)
  - Rationale: separating plotting/filter logic enables unit tests and reuse.

- **`analysis-dashboard/stats_utils.py`**
  - Fits a mixed effects model per population (`prop_logit ~ response` with random intercept per subject).
  - Applies Benjamini–Hochberg FDR correction across populations.
  - Rationale: mixed models account for repeated measures (multiple samples per subject), which is important for longitudinal designs.

- **`analysis-dashboard/streamlit_app.py`**
  - Streamlit UI: database loading (default or uploaded SQLite), filters, summary table, responder boxplots, and statistical results.

- **`tests/`**
  - Unit tests for ingestion, DB summary query, plotting/filter logic.
  - Rationale: ensures the schema and query outputs remain stable while iterating on the dashboard.

## Reproducing outputs

To reproduce the demo dashboard outputs exactly:

1. Build the database from the committed CSV:
   - `python analysis-dashboard/load_cell_counts.py`
2. Start the dashboard:
   - `streamlit run analysis-dashboard/streamlit_app.py`

You can also upload a different SQLite database into the sidebar as long as it follows the same schema.

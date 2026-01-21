.PHONY: install build-db run test

install:
	python -m pip install -r requirements.txt

build-db:
	[ -f analysis-dashboard/cell_counts.sqlite ] || python analysis-dashboard/load_cell_counts.py

run: install build-db
	streamlit run analysis-dashboard/streamlit_app.py --server.port 8501 --server.address 0.0.0.0

test: install
	pytest -q

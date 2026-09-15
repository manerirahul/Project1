.PHONY: help install profile transform quality load analysis all clean

PYTHON ?= python3

help:
	@echo "make install    - install Python dependencies"
	@echo "make profile    - profile the raw CSV        -> reports/data_profile.md"
	@echo "make transform  - clean + build star schema  -> data/processed/*.csv"
	@echo "make quality    - run the data-quality gate  -> reports/data_quality_report.md"
	@echo "make load       - apply DDL and load Postgres (needs .env)"
	@echo "make analysis   - charts + insights          -> reports/"
	@echo "make all        - profile -> transform -> quality -> load -> analysis"
	@echo "make clean      - remove generated artefacts"

install:
	$(PYTHON) -m pip install -r requirements.txt

profile:
	$(PYTHON) -m src.profile_data

transform:
	$(PYTHON) -m src.transform

quality:
	$(PYTHON) -m src.data_quality

load:
	$(PYTHON) -m src.load_to_postgres

analysis:
	$(PYTHON) -m src.analysis

# quality is a hard gate: the load only runs if every error-level check passes.
all: profile transform quality load analysis

clean:
	rm -f data/processed/*.csv reports/*.png reports/*.md

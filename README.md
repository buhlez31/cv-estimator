# CV Estimator

AI-powered case study system that analyzes CVs to estimate seniority, market salary, and provide growth recommendations.

## Setup

```bash
# Create virtualenv
python3.11 -m venv venv
source venv/bin/activate          # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements-dev.txt
pip install -e .                   # install cv_estimator as editable package

# Setup pre-commit hooks (one-time)
pre-commit install

# Configure API key
cp .env.example .env               # edit and add ANTHROPIC_API_KEY
```

## Run

```bash
# Streamlit UI
streamlit run cv_estimator/ui/app.py

# CLI
python scripts/run_analysis.py path/to/cv.pdf
```

## Status

WIP. Plná dokumentace bude doplněna po dokončení pipeline.

## Architecture

[High-level pipeline diagram TBD]

## Data sources

Salary data: [ISPV — Informační systém o průměrném výdělku](https://data.mpsv.cz/web/data/ispv-zamestnani), oficiální evidence MPSV ČR.

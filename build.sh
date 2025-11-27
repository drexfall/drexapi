#!/usr/bin/env bash
# Exit on error
set -o errexit

# Modify this line as needed for your package manager (pip, poetry, etc.)
pip install -r requirements.txt

# Convert static asset files
python manage.py collectstatic --no-input

# Apply any outstanding database migrations
python manage.py migrate

#Required for parser api
python -m spacy download en_core_web_sm
python -m nltk.downloader words
python -m nltk.downloader stopwords
"""Default configuration values."""

from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".libby" / "config.yaml"
DEFAULT_LIB_DIR = Path.home() / ".lib"

DEFAULT_CONFIG_YAML = """# libby configuration file
# Default location: ~/.libby/config.yaml

# Base directory for all libby data
# Subdirectories auto-generated:
#   - papers/      : PDF files and BibTeX metadata
#   - extract_task/: Failed extraction task logs
#   - search_results/: Websearch output files
lib_dir: ~/.lib

citekey:
  pattern: "{author}_{year}_{title}"
  author_words: 1
  title_words: 3
  title_chars_per_word: 0
  case: lowercase
  ascii_only: true
  ignored_words:
    - the
    - a
    - an
    - of
    - for
    - in
    - at
    - to
    - and
    - do
    - does
    - is
    - are
    - was
    - were
    - be
    - been
    - that
    - this
    - these
    - those
    - on
    - by
    - with
    - from

retry:
  max_retries: 5
  delays: [1, 2, 4, 15, 60]

ai_extractor:
  api_key: null
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
  max_tokens: 1000
"""
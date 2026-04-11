"""Default configuration values."""

from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".libby" / "config.yaml"
DEFAULT_PAPERS_DIR = Path.home() / ".lib" / "papers"

DEFAULT_CONFIG_YAML = """# libby configuration file
# Default location: ~/.libby/config.yaml

papers_dir: ~/.lib/papers

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
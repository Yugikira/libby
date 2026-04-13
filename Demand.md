# Project Overview

`libby` is a Python based **AI-friendly** CLI tool for scholar paper management with following functions.

- Get metadata: Retrieve metadata information with given doi, paper title or a pdf file and export to `.bib`, `.ris`, `json` or plain text. `libby` would also rename and backup the original file.

- Fetch PDF: Fetch PDF from legal OA sources such as `Crossref`, `Unpaywall`, `Semantic Scholar`, `arxiv`and [Sci-hub](https://sci-hub.ru).

- Web Search: Search `Semantic Scholar`, `Google Scholar` and `Crossref` for papers or authors and extract output a `json` format meta information (can be exported) or deliver through command line pipeline for `AI` usage.  

- Library management: Manage library database and a TUI support `vim` motion for human reader.

    - add_bib: Add entry to the library with bib and automatically detect and remove duplicates (keep the newest version).

    - add_pdf: Attach `.pdf` files to the entry.

    - add_note: Attach notes to the entry, supports `.md`, `.txt` and `.tex` files.

    - add_collection: Similar to `zotero` and `EndNote`, `libby` can group up papers by research topic or research work

    - search: perform various search (selection) methods to search paper in local library.

    - export: export search results to a file. Support file format of `.bib`, `.rif` and plain text like `.md` and `.txt`.

    - format_citekey: Reformat the citekey as required.

    - other library management functions that could be added in the future.

# Current Version Scope

In the current version, `libby` covers the first three functions.

# Commands and References

## `libby extract`

Retrieve metadata following `BibTex` standard.

1. If user provide `doi`, `libby` can extract information from `Crossref`. Refer to [Crossref API](./reference/rest-api-doc/) files. And `libby` will by default format a citekey with format like `first author family name_year_the first three words of the title connected by '_'`. The first three words should exclude function words or structure words such as "the", "a", "do", "does", "are", "is", etc.

2. The citekey formation could be configured by user with standard `BibTex` fields.

3. If user provide `title`, `libby` can extract information from from `Crossref` by querying the title in bibliography. If fail, use `Semantic Scholar` instead. And use [scholarly](https://github.com/scholarly-python-package/scholarly) as the final method.

4. If user provide PDF files, extract text for the first page and try to get the doi or title, then fallback to doi extract.

5. When the user provide PDF files, by default, after extracting metadata, `libby` will make a folder default to `~/.lib/papers/{citekey}/`. Then `libby` renames and moves the pdf file and the metadata to the folder. The default folder `~/.lib/papers/` can be configured by user. Provide a `--copy` argument, `libby` will use copy the original pdf file and rename the copy, leaving the original document unchanged. 

## `libby fetch`

Download PDF files by doi.

1. The default download path is `~/.lib/papers/temp/` and will be change to `user define path/temp/`

2. `libby extract` by doi or title, will automatically trigger `libby fetch` after getting the `doi`.

3. First `libby` will check if `Crossref` provide open access link, if so, download PDF file from the link with fetch.

4. Then `libby` will try `Unpaywall` -> `Semantic Scholar` -> `arxiv` -> `pubmed` to search for links. Refer to the [fetch scripts](./reference/paperfetch.py). The scripts exclude un-trustful hosts, `libby` will by pass this requirement.

5. For papers before 2022, `libby` will pdf from Sci-hub. Refer to [doi_hunter](./reference/doi_hunter) for more detail. Note that sci-hub could be blocked, remind the user and ai-agent to check currently available sci-hub website and change the configuration.

6. For more recent papers, user can use `Serpapi` Google Scholar endpoint to check if it provide a pdf link to fetch. This search method should be manually trigger for `Serpapi` is not free! Remind the user. 

## `libby websearch`

Search for paper metadata with keywords or semantic queries.

1. For author(s) and keywords in title, `libby` can use `Crossref` api to search within bibliography. For crossref would return too many results. By default, `libby` limits results to recent 2 years and the first 50 results. If user do not provide more restriction, remind the user to better limit to journal and year range.

2. `libby` can also perform `Semantic Scholar` search with various method. Refer to [Semantic Scholar API doc](https://api.semanticscholar.org/api-docs/) for more. By default return the first 50 results.

3. `libby` can also perform Google Scholar search with `scholarly` first and fallback to `Serpapi`. Refer to [serpapi api](https://serpapi.com/google-scholar-api). By default, return the first two page results.

4. User should be able to specify the websearch method. Otherwise, by default `libby` will perform all searches except search google scholar with serpapi (which requires user permission), combine the results and remove duplicates by doi.

## `libby man`

[To be added in future]

# Other requirements

1. Use `uv` to handle the environment.

2. Semantic Scholar API key should be set to environment variable `S2_API_KEY`, and Serpapi key shoulde be set to `SERPAPI_API_KEY`. Email should be set to environment variable `EMAIL`. Check whether these variables exist and return green/red status. If not exist, `libby` remind the user and skip for `Unpaywall` and `Serpapi` related methods, and add a more strict rate limit to `Semantic Scholar` related methods(with api, the rate limit is 1 request per second). 

3. The `extract`, `fetch` and `websearch` functions may return error code, if the error is `server error` or similar reasons(usually the return code is 500 or 503), wait for a timeout and retry. The maximum retry number default to 3.

4. Test functions with doi: "https://doi.org/10.1007/s11142-016-9368-9", and pdf file of `./example/test.pdf`, and a query of "corporate site visit".

5. Create `./skills/SKILL.md` with skills could be used by Claude Code to do works with `libby`.

6. Use `CHANGELOG.md` to record project major changes. 

7. Update `SKILL.md`, `CHANGELOG.md` and `README.md` everytime making a change.

# Note

- Use `chrome-dev-tools` mcp to read reference website if `Webfetch` is failed.



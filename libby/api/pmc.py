"""PubMed Central PDF URL builder."""


class PMCAPI:
    """PMC PDF URL builder (no API call needed).

    PMC PDFs are available at: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{id}/pdf/
    """

    @staticmethod
    def get_pdf_url(pmcid: str) -> str:
        """Build PMC PDF URL from PMCID.

        Args:
            pmcid: PubMed Central ID (with or without "PMC" prefix)

        Returns:
            Full PDF URL
        """
        # Ensure PMC prefix
        if not pmcid.upper().startswith("PMC"):
            pmcid = f"PMC{pmcid}"

        return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"

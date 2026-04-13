"""PubMed Central PDF URL builder."""


class PMCAPI:
    """PMC PDF URL builder (no API call needed).

    PMC PDFs are available at: https://pmc.ncbi.nlm.nih.gov/articles/PMC{id}/pdf/main.pdf

    Note: The URL format /pdf/ redirects to /pdf/main.pdf, but aiohttp may not
    properly handle this redirect for PDF downloads. Using the direct URL avoids
    potential issues with redirected PDF streams.
    """

    @staticmethod
    def get_pdf_url(pmcid: str) -> str:
        """Build PMC PDF URL from PMCID.

        Args:
            pmcid: PubMed Central ID (with or without "PMC" prefix)

        Returns:
            Full PDF URL with direct main.pdf format
        """
        # Ensure PMC prefix
        if not pmcid.upper().startswith("PMC"):
            pmcid = f"PMC{pmcid}"

        return f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/main.pdf"

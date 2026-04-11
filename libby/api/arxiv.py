"""arXiv PDF URL builder."""


class ArxivAPI:
    """arXiv PDF URL builder (no API call needed).

    arXiv PDFs are available at: https://arxiv.org/pdf/{arxiv_id}.pdf
    """

    @staticmethod
    def get_pdf_url(arxiv_id: str) -> str:
        """Build arXiv PDF URL from ID.

        Args:
            arxiv_id: arXiv identifier (e.g., "2301.12345" or "old-style:1234")

        Returns:
            Full PDF URL
        """
        # Strip any "arXiv:" prefix if present
        arxiv_id = arxiv_id.removeprefix("arXiv:").strip()
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

"""File operations."""

import shutil
from pathlib import Path

from libby.output.bibtex import BibTeXFormatter
from libby.models.metadata import BibTeXMetadata


class FileHandler:
    """Organize PDF and metadata files."""

    def __init__(self, papers_dir: Path):
        self.papers_dir = papers_dir

    def organize_pdf(
        self,
        pdf_path: Path,
        metadata: BibTeXMetadata,
        copy: bool = False,
        output_dir: Path | None = None,
    ) -> Path:
        """Organize PDF into target directory.

        Args:
            pdf_path: Source PDF file path
            metadata: Extracted metadata with citekey
            copy: Copy PDF instead of moving
            output_dir: Override target directory (if specified, use this instead of papers_dir)

        Returns:
            Target directory path
        """
        # Use output_dir if specified, otherwise default papers_dir
        target_dir = output_dir or (self.papers_dir / metadata.citekey)
        target_dir.mkdir(parents=True, exist_ok=True)

        target_pdf = target_dir / f"{metadata.citekey}.pdf"
        if copy:
            shutil.copy2(pdf_path, target_pdf)
        else:
            shutil.move(str(pdf_path), str(target_pdf))

        target_bib = target_dir / f"{metadata.citekey}.bib"
        target_bib.write_text(BibTeXFormatter().format(metadata), encoding="utf-8")

        return target_dir

    def organize_pdf_bytes(self, pdf_bytes: bytes, metadata: BibTeXMetadata, output_dir: Path | None = None) -> Path:
        """Save PDF bytes directly to target folder.

        Args:
            pdf_bytes: PDF file content
            metadata: Extracted metadata with citekey
            output_dir: Override target directory (if specified, use this instead of papers_dir)

        Returns:
            Target directory path
        """
        target_dir = output_dir or (self.papers_dir / metadata.citekey)
        target_dir.mkdir(parents=True, exist_ok=True)

        target_pdf = target_dir / f"{metadata.citekey}.pdf"
        target_pdf.write_bytes(pdf_bytes)

        target_bib = target_dir / f"{metadata.citekey}.bib"
        target_bib.write_text(BibTeXFormatter().format(metadata), encoding="utf-8")

        return target_dir
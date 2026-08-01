"""Conservative LaTeX to SATySFi conversion through Pandoc JSON AST."""

from .converter import ConversionResult, convert_document

__all__ = ["ConversionResult", "convert_document"]
__version__ = "0.1.0a0"

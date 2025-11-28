from .pdf_converter import PDFConverter
from .excel_converter import ExcelConverter
from .docx_converter import DocxConverter
from .drawio_converter import DrawioConverter

# Реестр конвертеров
_converters = {
    "pdf": PDFConverter,
    "xlsx": ExcelConverter,
    "xls": ExcelConverter,
    "xml": DrawioConverter,
    "docx": DocxConverter,
}

def get_converter(ext: str):
    return _converters.get(ext)

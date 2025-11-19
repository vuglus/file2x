class BaseConverter:
    """
    Базовый класс для всех конвертеров.
    На вход — путь файла, на выход — строка (Markdown/текст).
    """

    def convert(self, path: str) -> str:
        raise NotImplementedError("convert() must be implemented in subclass")
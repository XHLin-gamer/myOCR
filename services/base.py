from abc import ABC, abstractmethod

class BaseOCRService(ABC):
    """
    Abstract Base Class defining the contract for OCR services.
    Enables swapping between local engines and cloud APIs seamlessly.
    """
    @abstractmethod
    def image_to_markdown(self, image_path: str) -> str:
        """
        Convert a scanned image to formatted Markdown.
        """
        pass

######## LIBRARIES ########

from textual.widgets import Static


######## BORDER STATIC ########

class BorderStatic(Static):
    """Dynamic-width widget that renders repeated characters synchronously during layout."""

    def __init__(self, char: str, **kwargs) -> None:
        self._char = char
        super().__init__(**kwargs)


    def render(self) -> str:
        width = self.size.width if self.size.width > 0 else 80
        return self._char * width

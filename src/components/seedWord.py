######## LIBRARIES ########

from textual.events import Click, Blur, Focus
from textual.widgets import Input
from textual import work
import asyncio


######## SEED WORD WIDGET ########

class SeedWord(Input):
    """A custom input widget for entering or displaying seed words with a solid block masking mechanism."""

    def __init__(self, index: int, readonly: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.index = index
        self.isReadonly = readonly
        self._realValue = ""
        self._isMasked = True

        self.placeholder = f"Word #{self.index + 1}"

        if self.isReadonly:
            self.disabled = True

        self.add_class("seed-word")


    def on_input_changed(self, event: Input.Changed) -> None:
        """Track the real value as the user types."""
        # Ignore changes if the value is just our mask blocks
        if event.value and all(c == "█" for c in event.value):
            return

        self._realValue = event.value


    def on_focus(self, event: Focus) -> None:
        """Reveal the real value when focused for editing."""
        if not self.isReadonly:
            self._isMasked = False
            self.value = self._realValue


    def on_blur(self, event: Blur) -> None:
        """Mask the value when focus is lost."""
        if not self.isReadonly:
            self._applyMask()


    async def on_click(self, event: Click) -> None:
        """Temporarily reveal the word when clicked, especially useful in readonly mode."""
        if self._isMasked and self._realValue:
            self._temporarilyReveal()


    @work
    async def _temporarilyReveal(self) -> None:
        """Temporarily reveal the word for 2 seconds."""
        self._isMasked = False
        self.value = self._realValue

        await asyncio.sleep(2)

        if not self.has_focus or self.isReadonly:
            self._applyMask()


    def _applyMask(self) -> None:
        """Apply the solid white block mask."""
        if self._realValue:
            self._isMasked = True
            self.value = "█" * len(self._realValue)


    def setRealValue(self, val: str) -> None:
        """Set the real value programmatically (useful for decode screen)."""
        self._realValue = val
        self._applyMask()


    def getRealValue(self) -> str:
        """Get the real value."""
        return self._realValue
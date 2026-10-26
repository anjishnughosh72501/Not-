# MarkSnap

> Shape-driven screen capture & annotation companion for Windows 10/11.

Point at anything, draw a shape, and your PC understands what you meant.

## Features

- **Zero-UI Invocation**: Global hotkey (`Ctrl+Shift+D`) freezes your desktop with an aesthetic background blur indicating annotate mode.
- **Floating Hotbar**:
  - **Pens**: Ballpoint, Fineliner, Marker
  - **Highlighters**: Yellow, Green, Cyan semi-transparent highlights
  - **Pointer**: Dynamic arrow callouts
  - **Ask AI Mode**: Draw a box to send screen regions to an AI vision model
  - **Save & Dismiss**: Press `Enter` to save or `Esc` to cancel
- **Gesture Vocabulary**:
  - **Box**: Save region to disk as PNG/JPG
  - **Circle**: Extract text inside with OCR and copy directly to clipboard
  - **Underline**: Save the entire annotated screen
  - **Arrow**: Send region + annotation to AI Vision
- **Separate Companion App** (`run_companion.py`):
  - **Library**: Searchable capture index, tags, full previews, and Recycle Bin deletion
  - **Hotkeys**: Interactive hotkey recorder
  - **Gestures**: Enable/disable shapes, action routing, and sensitivity slider with interactive test canvas
  - **Appearance**: Customize ink and gesture colors, stroke width, and toast notifications
  - **Storage**: Directory picker, filename patterns, auto-deletion rules
  - **AI Vision**: Secure API key management stored in Windows Credential Manager via `keyring`

## Requirements

- Windows 10 or 11
- Python 3.11+
- Tesseract OCR (optional, for circle OCR gesture)

## Installation

```bash
git clone https://github.com/anjishnughosh72501/Not-.git
cd Not-
pip install -r requirements.txt
```

## Running MarkSnap

1. **Start the background capture overlay**:
   ```bash
   python marksnap.py
   ```
2. **Launch the MarkSnap Companion UI**:
   ```bash
   python run_companion.py
   ```

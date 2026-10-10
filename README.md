# Labelizer4x6

**Version 2.0.0 of [EasyLabel Extractor](https://github.com/mershonc/EasyLabel-Extractor)**

A free Windows desktop utility for extracting shipping labels from return PDFs and formatting them for 4 × 6 inch thermal label printers. Created by Carson.

Labelizer4x6 replaces the original Tkinter interface with a modern dark-purple desktop UI. Everything is processed locally, without uploading your PDFs.

## Download

Once released, download the **Labelizer4x6.exe** file from [GitHub Releases](https://github.com/mershonc/EasyLabel-Extractor/releases). It is a single-file Windows executable; a separate Python installation is not required to run it.

> **v2.0.0 release preparation:** The source code is currently under review. The standalone Windows executable will be uploaded to the release separately after local testing.

## Features

- **Auto-find label:** Automatically locate a likely shipping-label rectangle within a return document.
- **Manual crosshair selection:** Drag around any area of a PDF and preview it as a 4 × 6 label.
- **Multiple PDFs:** Add files through the file picker or drag PDFs into the left panel. Remove individual entries without deleting their originals.
- **Live output preview:** Verify the label before saving or printing.
- **Rotation:** Rotate a label by 90° in either direction, including upside-down labels.
- **Sizing:** Stretch selection to 4 × 6, fill the page by cropping edges, or fit the entire selection with margins.
- **Undo crop:** Restore the original page and select a different region.
- **Print directly:** Choose a Windows printer through the print dialog.
- **Save as PDF:** Create a true 4 × 6 inch PDF named `OriginalFilename_YYYY-MM-DD_HH-MM-SS_4x6.pdf`.
- **Optional PDF viewer:** Optionally open the saved output in your default PDF application.

## Using Labelizer4x6

1. Run `Labelizer4x6.exe` and add one or more PDFs.
2. Choose the PDF and page containing the label.
3. Use **Auto-find label** or **Manual crosshair crop** to select it.
4. Review the preview. Adjust sizing and rotation if necessary.
5. Click **Print 4×6 Label** or **Save 4×6 Label PDF**. The open-after-saving checkbox is optional and off by default.

### Barcode and printer safety

The **Stretch selection** option fills the whole page but can distort barcodes when the selection is not already close to a 2:3 aspect ratio. For maximum scan reliability, prefer **Fit entire selection** or crop more closely to the label without distorting it. Verify the printed label before shipping.

Printing requires a configured printer and compatible Windows printer driver. In the printer preferences, select **4 × 6 inch** label stock and confirm the orientation and scaling.

## Build from source (Windows)

You will need Python 3.11 or 3.12 on Windows.

```bat
git clone https://github.com/mershonc/EasyLabel-Extractor.git
cd EasyLabel-Extractor
build_windows.bat
```

The build script installs dependencies from `requirements.txt`, generates artwork with `generate_assets.py`, then packages the application with PyInstaller. The standalone executable appears at:

```text
dist\Labelizer4x6.exe
```

To run the source directly:

```bat
py -m pip install -r requirements.txt
py generate_assets.py
py labelizer.py
```

## Version history

- **v2.0.0:** Labelizer4x6 with a redesigned interface, automatic label detection, drag-and-drop, cropping, rotation, sizing options, direct printing, and timestamped exports.
- **v1.0.0:** Carson's EasyLabel Extractor, a simple manual PDF region-selection utility. The original source remains available in the Git history and original release.

See [CHANGELOG.md](CHANGELOG.md) for details and [RELEASE_NOTES_v2.0.0.md](RELEASE_NOTES_v2.0.0.md) for the release description.

## License

This project is licensed under the **GNU General Public License v3.0**, consistent with the original repository. See [LICENSE](LICENSE).

Created by Carson.

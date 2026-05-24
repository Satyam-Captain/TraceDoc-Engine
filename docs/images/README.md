# Architecture images

Export diagrams from [`../architecture.drawio`](../architecture.drawio) and place PNG or SVG files here for README, Streamlit, and hosted demos.

## Recommended exports

| File | Source page in draw.io |
|------|-------------------------|
| `architecture-overview.png` | 1. System Overview |
| `architecture-document-pipeline.png` | 2. Document Processing |
| `architecture-qa-flow.png` | 3. Question Answering |
| `architecture-storage-modules.png` | 4. Storage & Modules |

## Steps (diagrams.net)

1. Open https://app.diagrams.net → **Open Existing** → select `docs/architecture.drawio`.
2. Use the **tabs at the bottom** to switch pages before exporting each diagram.
3. **File → Export as → PNG** (300 DPI for slides, or SVG for crisp web).
4. Save into this folder with the names above.
5. Commit and push so GitHub and Streamlit Cloud can serve the images.

Optional: link images from the root README after export.

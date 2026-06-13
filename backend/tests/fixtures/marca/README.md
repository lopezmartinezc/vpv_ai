# Marca cromo fixtures

Real press-clipping images used by `test_marca_image_integration.py`
to verify per-player rating extraction against a pixel-verified
ground truth.

## Files (expected)

- `marca.png` — Mexico 2-0 Sudáfrica (31 players)
- `img_a.jpeg` — Canadá 1-1 Bosnia (32 players)
- `img_b.png` — Corea 2-1 Chequia (no ground truth recorded, smoke-test only)
- `img_d.png` — USA 4-1 Paraguay (31 players)

## Why they're committed

The reference extractor scores 94/94 on the 3 fixtures with ground
truth. Keeping those fixtures + the `_GROUND_TRUTH` dict in
`test_marca_image_integration.py` gives a strict no-regression gate
for changes to `_count_stars`, `_has_dash`, or `_detect_row_centers`.

## License

Newspaper press clippings, used here as fair-use technical fixtures
for OCR development. Marca retains copyright on the originals.

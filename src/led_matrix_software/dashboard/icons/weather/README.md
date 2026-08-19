# Weather Icons (16x16 monochrome BMP)

This directory holds optional hand-drawn 16x16 monochrome BMP files used as
inline weather icons in the dashboard scroll.

## Naming

The filename (without the `.bmp` extension) must match a key returned by
the weather scraper. Typical keys:

| Filename        | Source / meaning                 |
|-----------------|----------------------------------|
| `晴.bmp`        | sunny / clear                    |
| `曇.bmp`        | cloudy                           |
| `曇り.bmp`      | cloudy (alternate form)          |
| `雨.bmp`        | rain                             |
| `雪.bmp`        | snow                             |
| `雷.bmp`        | thunder                          |
| `強風注意報.bmp`| 強風 warning (displayed as alert)|

Matching is exact; fall-through substring matching is applied for compound
descriptions (e.g. `晴時々曇` will fall back to whatever icon you provide for
`晴`).

## Format

- 16 x 16 pixels
- Monochrome (1 bit per pixel)
- BMP format supported by OpenCV (`cv2.imread` with `IMREAD_GRAYSCALE`)
- Pixels above 128 in the source file are treated as ON; below 128 as OFF

## Fallback

If no BMP is provided for a given weather string, the dashboard falls back
to rendering the original text character (`晴`, `曇`, `雨`, etc.) instead
of the icon.

To disable icon rendering entirely, simply leave this directory empty.
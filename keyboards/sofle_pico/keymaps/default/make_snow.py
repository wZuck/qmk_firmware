#!/usr/bin/env python3
"""Turn the two `oled_snow*.pdf` drawings into OLED art.

`build_soflepico/oled_snow1.pdf` and `oled_snow2.pdf` each carry one drawing of
the two snowboarders, and the two differ only in the left one's arm: down in
one, up in a peace sign in the other. Downsized to the panel they make a
two-frame loop - a wave - which is what "the snow pair" art set is.

    python3 make_snow.py                      # writes snow_1.png / snow_2.png
    python3 make_snow.py --print-only         # report sizes, write nothing

What it does, and why each step is needed at 64 px wide:

  * crop to the ink in *both* frames at once (a shared box, so the pair does not
    jitter between frames);
  * 3 px unsharp mask before the downscale - it is the difference between the
    line art surviving the 16:1 reduction and turning to mush;
  * threshold at 160, which keeps the thin goggle and zip lines that a lower
    cutoff drops and a higher one closes up;
  * drop blobs under 4 px. The JPEG is compressed, so downscaling turns its
    ringing into single-pixel specks all over the background; without this the
    panel looks dirty rather than drawn.

The result is 64 px wide and keeps the drawings' aspect ratio (~62 px tall),
centred vertically on the 128 px canvas. There is nothing to fill the rest with
- the drawings are landscape and the panel is portrait - so the pair sits in the
middle with blank bands above and below.

Reading the PDFs needs the standard library only (`zlib` is not even used: the
image is a DCTDecode JPEG, so the raw stream is the JPEG). The image processing
needs Pillow:

    python3 -m pip install pillow

After this, convert to the display format and paste the result into
`oled_snow.h` (img2c.py's output is a single frame, so the final header is
hand-assembled from two runs - see the notes in oled_snow.h):

    python3 img2c.py snow_1.png --height 128 --name snow_1 -o snow_1.h
    python3 img2c.py snow_2.png --height 128 --name snow_2 -o snow_2.h

`--height 128` because a frame of an animation is the whole canvas, not just
the part with ink.
"""

import argparse
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE)))), "build_soflepico")
PDFS = ("oled_snow1.pdf", "oled_snow2.pdf")

CANVAS_W = 64
CANVAS_H = 128

CROP_MARGIN = 0     # px of padding around the shared ink box
SHARPEN_RADIUS = 3
SHARPEN_PERCENT = 160
THRESHOLD = 160     # 0-255; higher keeps more of the thin lines
MIN_BLOB = 4        # px; anything smaller after downscaling is JPEG noise


def jpeg_from_pdf(path):
    """The single DCTDecode image stream of a one-image PDF.

    The drawings are embedded as JPEG, so the stream is handed to Pillow as is
    - there is no need for a PDF library, or even zlib.
    """
    data = open(path, "rb").read()
    m = re.search(rb"/Subtype\s*/Image", data)
    if m is None:
        raise SystemExit("%s: no image in this PDF" % path)

    # The image object is the one whose header carries /Width; take the stream
    # that follows it.
    start = data.find(b"stream", m.start())
    if start < 0:
        raise SystemExit("%s: image object has no stream" % path)
    start += len(b"stream")
    while data[start : start + 1] in (b"\r", b"\n"):
        start += 1
    end = data.find(b"endstream", start)
    if end < 0:
        raise SystemExit("%s: unterminated image stream" % path)

    raw = data[start:end]
    soi = raw.find(b"\xff\xd8\xff")
    eoi = raw.rfind(b"\xff\xd9")
    if soi < 0 or eoi < 0:
        raise SystemExit("%s: stream is not a JPEG" % path)
    return raw[soi : eoi + 2]


def shared_ink_box(images, threshold=128):
    """The union of both frames' ink, so the pair crops identically.

    Cropping each frame to its own box would let the pair shift sideways
    between frames, which on a 64 px panel reads as a twitch.
    """
    import numpy as np

    x0 = y0 = None
    x1 = y1 = None
    for im in images:
        a = np.asarray(im)
        ys, xs = np.nonzero(a < threshold)
        if len(xs) == 0:
            raise SystemExit("a frame is blank")
        bx0, bx1 = int(xs.min()), int(xs.max()) + 1
        by0, by1 = int(ys.min()), int(ys.max()) + 1
        x0 = bx0 if x0 is None else min(x0, bx0)
        y0 = by0 if y0 is None else min(y0, by0)
        x1 = bx1 if x1 is None else max(x1, bx1)
        y1 = by1 if y1 is None else max(y1, by1)
    return (x0 - CROP_MARGIN, y0 - CROP_MARGIN, x1 + CROP_MARGIN, y1 + CROP_MARGIN)


def despeckle(mask, min_px):
    """Drop 8-connected blobs smaller than `min_px`.

    Plain flood fill: the frames are 64 x 62, so even in Python this is
    instant, and it keeps the script free of scipy.
    """
    import numpy as np

    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = mask.copy()
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or seen[y, x]:
                continue
            queue = collections.deque([(y, x)])
            seen[y, x] = True
            blob = []
            while queue:
                cy, cx = queue.popleft()
                blob.append((cy, cx))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            queue.append((ny, nx))
            if len(blob) < min_px:
                for cy, cx in blob:
                    out[cy, cx] = False
    return out


def to_canvas(image, box):
    """One drawing -> a whole 64 x 128 canvas, 1-bit, ink = black."""
    import numpy as np
    from PIL import Image, ImageFilter, ImageOps

    crop = image.crop(box)
    width = CANVAS_W
    height = max(8, int(round(crop.height * width / crop.width)))

    # Sharpen at full resolution, then shrink: the other order has nothing left
    # to sharpen.
    crop = crop.filter(ImageFilter.UnsharpMask(radius=SHARPEN_RADIUS, percent=SHARPEN_PERCENT, threshold=2))
    small = ImageOps.autocontrast(crop.resize((width, height), Image.LANCZOS))

    ink = despeckle(np.asarray(small) < THRESHOLD, MIN_BLOB)

    canvas = np.full((CANVAS_H, CANVAS_W), 255, dtype=np.uint8)
    top = (CANVAS_H - height) // 2
    canvas[top : top + height][ink] = 0
    return Image.fromarray(canvas), height, top


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf-dir", default=PDF_DIR, help="where the oled_snow*.pdf files are (default: %(default)s)")
    ap.add_argument("--print-only", action="store_true", help="report sizes without writing the PNGs")
    args = ap.parse_args()

    try:
        from PIL import Image
    except ImportError:
        sys.exit("needs Pillow: python3 -m pip install pillow")

    paths = [os.path.join(args.pdf_dir, name) for name in PDFS]
    for p in paths:
        if not os.path.exists(p):
            sys.exit("missing %s (pass --pdf-dir)" % p)

    images = [Image.open(__import__("io").BytesIO(jpeg_from_pdf(p))).convert("L") for p in paths]
    box = shared_ink_box(images)
    print("shared crop box: x %d-%d  y %d-%d  (%d x %d)" % (box[0], box[2], box[1], box[3], box[2] - box[0], box[3] - box[1]))

    canvases = []
    for i, im in enumerate(images):
        canvas, height, top = to_canvas(im, box)
        canvases.append(canvas)
        ink = int((__import__("numpy").asarray(canvas) < 128).sum())
        print("  snow_%d: %dx%d on the canvas, rows %d-%d, %d ink px" % (i + 1, CANVAS_W, height, top, top + height - 1, ink))

    if args.print_only:
        return

    for i, canvas in enumerate(canvases):
        out = os.path.join(HERE, "snow_%d.png" % (i + 1))
        canvas.save(out)
        print("wrote", out)

        # The inverted pair, for the "inverted snow" screen: the snowboarders in
        # dark on a lit panel instead of lit on a dark one. It is a straight
        # pixel flip, so it is written from the same canvas rather than
        # re-thresholded from the PDF.
        inv = Image.eval(canvas, lambda v: 255 - v)
        out = os.path.join(HERE, "snow_%d_inv.png" % (i + 1))
        inv.save(out)
        print("wrote", out)

    # How much actually moves, so a silent crop mistake is visible.
    import numpy as np

    a = np.asarray(canvases[0]) < 128
    b = np.asarray(canvases[1]) < 128
    print("frames differ in %d px" % int((a ^ b).sum()))


if __name__ == "__main__":
    main()

"""Blank out the document-level JavaScript KiCad writes into every schematic PDF (a helper for pop-ups).

The object is overwritten with an empty dictionary padded to the same length, so every offset in the
file stays valid and links, bookmarks and metadata are untouched.
Usage: clean_pdf.py <file.pdf>
"""
import re
import sys

path = sys.argv[1]
data = open(path, "rb").read()
size, found = len(data), 0
for m in list(re.finditer(rb"\d+ 0 obj\s*(<<\s*/JavaScript\b.*?)\s*endobj", data, re.S)):
    body = m.group(1)
    data = data[:m.start(1)] + b"<<" + b" " * (len(body) - 4) + b">>" + data[m.end(1):]
    found += 1
assert len(data) == size
left = [k for k in (b"/JavaScript", b"/JS ", b"/JS(") if k in data]
assert not left, f"JavaScript still referenced: {left}"
open(path, "wb").write(data)
print(f"{path}: {found} JavaScript object(s) blanked")

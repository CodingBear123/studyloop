"""Inline the two font files into src/index.src.html -> index.html."""
import base64, pathlib
root = pathlib.Path(__file__).parent
b64 = lambda f: base64.b64encode((root / "fonts" / f).read_bytes()).decode()
html = (root / "src/index.src.html").read_text()
html = html.replace("__ARCHIVO__", b64("archivo-black-latin.woff2")).replace("__GROTESK__", b64("space-grotesk-latin.woff2"))
(root / "index.html").write_text(html)
print("wrote index.html", len(html), "bytes")

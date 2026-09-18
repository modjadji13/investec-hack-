"""Extract the supplied rules and compare the source data, without modifying them."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
import pymupdf

downloads = Path(r"C:\Users\modja\Downloads")
output = Path("out/optimization")
output.mkdir(parents=True, exist_ok=True)
doc = pymupdf.open(downloads / "problem-statement.pdf")
text = []
for i, page in enumerate(doc):
    text.append(f"\n--- PAGE {i + 1} ---\n" + page.get_text())
    page.get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3)).save(output / f"rules-{i+1}.png")
(output / "rules.txt").write_text("\n".join(text), encoding="utf-8")
print("\n".join(text))
with ZipFile(downloads / "additional-resources.zip") as archive:
    for item in archive.infolist():
        if not item.is_dir():
            local = Path("data") / Path(item.filename).name
            print(item.filename, "identical:", local.read_bytes() == archive.read(item))
for n in range(1, 5):
    a = json.loads((downloads / f"{n}.json").read_text())
    b = json.loads(Path(f"data/level{n}.json").read_text())
    print("Level", n, "matches supplied:", a == b)
for n, filename in enumerate(["LEVEL1_v2_submission.json", "LEVEL2_submission_1.json",
                              "LEVEL3_submission - Copy.json", "LEVEL4_submission.json"], 1):
    a = json.loads((downloads / filename).read_text())
    b = json.loads(Path(f"data/level{n}_submission.json").read_text())
    print("Submission", n, "matches supplied:", a == b)

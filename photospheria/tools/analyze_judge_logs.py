import glob
import hashlib
import os
import re


seen = set()
for path in glob.glob(r"C:\Users\modja\Downloads\*evaluation*.log"):
    raw = open(path, "rb").read()
    digest = hashlib.sha256(raw).hexdigest()
    if digest in seen:
        continue
    seen.add(digest)
    text = raw.decode(errors="replace")
    dims = re.search(r"loaded level \((\d+x\d+), (\d+) ticks\)", text)
    stats = re.search(r"PlantSim statistics: (.*?)(?:\n\[|\Z)", text, re.S)
    score = re.search(r"'score': ([0-9.]+)", stats.group(1) if stats else "")
    counts = re.search(r"'plant_counts': array\(\[(.*?)\]\)", stats.group(1) if stats else "", re.S)
    rejected = re.findall(r"Placement denied for plant (\d+) at .*?: (.*)", text)
    rejection_counts = {
        int(index): sum(item_index == index for item_index, _ in rejected)
        for index, _ in rejected
    }
    print(f"\n{os.path.basename(path)}")
    print("level", dims.groups() if dims else None, "score", score.group(1) if score else None)
    print("rejections", len(rejected), rejection_counts)
    print("plant_counts", " ".join(counts.group(1).split()) if counts else "none")

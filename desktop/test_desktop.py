import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from app import process

def test_offline_file_roundtrip(tmp_path):
    path=tmp_path/"notes.txt";path.write_text("Order 1 shipped\nOrder 2 shipped\nOrder 1 shipped")
    r=process([str(path)])
    assert r["stats"]["lossless_verified"]
    assert r["output"]["text"]
    assert json.dumps({"records":r["records"],"map":r["map"]})

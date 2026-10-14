import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine_routes import _cache_key

def test_order_matters():
    assert _cache_key([b"a",b"b"],{},3)!=_cache_key([b"b",b"a"],{},3)

def test_source_names_and_accounts_matter():
    assert _cache_key([b"one.txt\x00x"],{},3)!=_cache_key([b"two.txt\x00x"],{},3)
    assert _cache_key([b"user1",b"x"],{},3)!=_cache_key([b"user2",b"x"],{},3)

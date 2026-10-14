"""Bundle offline TokenForge and pre-cache tokenizer encoding."""
import os,sys,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
cache=root/"desktop"/"tiktoken_cache";cache.mkdir(exist_ok=True)
os.environ["TIKTOKEN_CACHE_DIR"]=str(cache)
import tiktoken
tiktoken.get_encoding("cl100k_base")
if not list(cache.iterdir()):raise RuntimeError("Tokenizer cache unavailable")
cmd=[sys.executable,"-m","PyInstaller","--noconfirm","--clean","--windowed",
     "--name","TokenForge","--paths",str(root/"backend"),"--hidden-import","tiktoken_ext.openai_public",
     "--add-data",str(root/"backend")+os.pathsep+"backend",
     "--add-data",str(cache)+os.pathsep+"tiktoken_cache",
     "--distpath",str(root/"desktop"/"dist"),"--workpath",str(root/"desktop"/"build"),
     "--specpath",str(root/"desktop"/"build"),str(root/"desktop"/"app.py")]
if sys.platform=="darwin":
    cmd[3:3]=["--osx-bundle-identifier","com.terranextech.tokenforge"]
code=subprocess.call(cmd)
if code==0 and sys.platform=="darwin":
    import plistlib
    info=root/"desktop"/"dist"/"TokenForge.app"/"Contents"/"Info.plist"
    if not info.exists(): raise RuntimeError("macOS application bundle missing")
    with info.open("rb") as fp: data=plistlib.load(fp)
    data["CFBundleDocumentTypes"]=[
        {"CFBundleTypeName":"Text and data for TokenForge",
         "CFBundleTypeRole":"Viewer",
         "LSHandlerRank":"Alternate",
         "LSItemContentTypes":["public.plain-text","public.comma-separated-values-text",
                               "public.json","public.zip-archive","com.adobe.pdf"]}
    ]
    with info.open("wb") as fp: plistlib.dump(data,fp)
raise SystemExit(code)

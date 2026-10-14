"""Offline TokenForge desktop UI. No account, database, or network calls."""
import json
import os
import sys
import threading
import queue
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

ROOT=Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
if (ROOT/"tiktoken_cache").exists():
    os.environ["TIKTOKEN_CACHE_DIR"]=str(ROOT/"tiktoken_cache")
sys.path.insert(0,str(ROOT/"backend"))
# Import the optimizer lazily in the worker so the window appears first.
MAX_BYTES=50*1024*1024

def process(paths, threshold=.82, guard="facts", budget=None):
    from optimizer import optimize_sources
    from parsers import parse_upload
    sources=[]; total=0
    for filename in paths:
        p=Path(filename); total+=p.stat().st_size
        if total>MAX_BYTES:
            raise ValueError("Selected files exceed the 50 MB limit.")
        sources.extend(parse_upload(p.read_bytes(),p.name))
    if not sources: raise ValueError("No readable text found.")
    result=optimize_sources(sources,threshold=threshold,guard=guard,budget=budget)
    if not result["stats"]["lossless_verified"]:
        raise ValueError("Parsed-fragment reconstruction did not verify.")
    return result

class Desktop:
    def __init__(self,root):
        self.root=root; self.files=[]; self.result=None; self.events=queue.Queue()
        root.title("TokenForge — Offline"); root.geometry("900x650")
        if sys.platform == "darwin":
            root.createcommand("::tk::mac::OpenDocument", self.open_mac_documents)
        box=ttk.Frame(root,padding=16);box.pack(fill="both",expand=True)
        ttk.Label(box,text="TokenForge · Offline",font=("Arial",20,"bold")).pack(anchor="w")
        ttk.Label(box,text="Files stay on this computer. No login or internet required.").pack(anchor="w",pady=(0,10))
        commands=ttk.Frame(box);commands.pack(fill="x")
        ttk.Button(commands,text="Add files",command=self.add).pack(side="left")
        ttk.Button(commands,text="Clear",command=self.clear).pack(side="left",padx=8)
        self.list=tk.Listbox(box,height=6);self.list.pack(fill="x",pady=8)
        options=ttk.Frame(box);options.pack(fill="x")
        ttk.Label(options,text="Similarity:").pack(side="left")
        self.threshold=tk.StringVar(value="0.82")
        ttk.Entry(options,textvariable=self.threshold,width=8).pack(side="left",padx=6)
        ttk.Label(options,text="Guard:").pack(side="left")
        self.guard=tk.StringVar(value="facts")
        ttk.Combobox(options,textvariable=self.guard,values=["facts","strict","off"],width=8,state="readonly").pack(side="left",padx=6)
        ttk.Label(options,text="Token budget (optional):").pack(side="left")
        self.budget=tk.StringVar()
        ttk.Entry(options,textvariable=self.budget,width=9).pack(side="left",padx=6)
        buttons=ttk.Frame(box);buttons.pack(fill="x",pady=10)
        self.run=ttk.Button(buttons,text="Optimize",command=self.start);self.run.pack(side="left")
        self.save=ttk.Button(buttons,text="Save TXT",command=self.save_txt,state="disabled");self.save.pack(side="left",padx=5)
        self.bundle=ttk.Button(buttons,text="Save recovery bundle",command=self.save_bundle,state="disabled");self.bundle.pack(side="left",padx=5)
        self.copy=ttk.Button(buttons,text="Copy full output",command=self.copy_result,state="disabled");self.copy.pack(side="left",padx=5)
        self.status=tk.StringVar(value="Ready")
        ttk.Label(box,textvariable=self.status).pack(anchor="w")
        self.text=tk.Text(box,wrap="none");self.text.pack(fill="both",expand=True,pady=8)
        self.text.configure(state="disabled")
        root.after(100,self.poll)
        initial=[arg for arg in sys.argv[1:] if not arg.startswith("-psn_")]
        if initial:
            root.after(50,lambda: self.open_paths(initial,auto_start=True))
    def open_paths(self, paths, auto_start=False):
        added=0
        for raw in paths:
            path=Path(raw).expanduser()
            if not path.is_file():
                self.status.set("A selected path is not a readable file: "+str(raw))
                continue
            normalized=str(path.resolve())
            if normalized not in self.files:
                self.files.append(normalized)
                self.list.insert("end",normalized)
                added+=1
        if auto_start and added and self.run.cget("state")!="disabled":
            self.start()
        elif added:
            self.status.set(str(len(self.files))+" files ready")
        return added

    def open_mac_documents(self,*paths):
        self.open_paths(paths,auto_start=True)

    def add(self):
        self.open_paths(filedialog.askopenfilenames())
    def clear(self):
        self.files=[];self.list.delete(0,"end")
    def start(self):
        if not self.files:return messagebox.showinfo("Files","Choose at least one file.")
        try:
            t=float(self.threshold.get());b=int(self.budget.get()) if self.budget.get().strip() else None
            if not .5<=t<=1 or (b is not None and b<50):raise ValueError("Similarity must be 0.5–1; budget at least 50.")
        except ValueError as e:return messagebox.showerror("Settings",str(e))
        self.result=None;self.run.configure(state="disabled")
        for btn in [self.save,self.bundle,self.copy]:btn.configure(state="disabled")
        self.status.set("Optimizing locally…")
        # Read Tk state on the UI thread; workers must not access Tk variables.
        chosen_files = self.files[:]
        chosen_guard = self.guard.get()
        def worker():
            try:self.events.put(("ok",process(chosen_files,t,chosen_guard,b)))
            except Exception as e:self.events.put(("error",str(e)))
        threading.Thread(target=worker,daemon=True).start()
    def poll(self):
        try:
            while True:
                kind,value=self.events.get_nowait();self.run.configure(state="normal")
                if kind=="error":self.status.set("Failed");messagebox.showerror("Processing",value);continue
                self.result=value;s=value["stats"];output=value["output"]["text"]
                self.status.set(f'{s["tokens_before"]:,} → {s["tokens_after"]:,} tokens · {s["token_reduction_pct"]}% reduction · parsed fragments verified')
                self.text.configure(state="normal");self.text.delete("1.0","end")
                self.text.insert("end",output[:100000]);self.text.configure(state="disabled")
                for btn in [self.save,self.bundle,self.copy]:btn.configure(state="normal")
        except queue.Empty:pass
        self.root.after(100,self.poll)
    def save_txt(self):
        p=filedialog.asksaveasfilename(defaultextension=".txt",filetypes=[("Text","*.txt")])
        if p:Path(p).write_text(self.result["output"]["text"],encoding="utf-8")
    def save_bundle(self):
        p=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("JSON","*.json")])
        if p:
            r=self.result
            Path(p).write_text(json.dumps({"stats":r["stats"],"records":r["records"],"map":r["map"]},ensure_ascii=False),encoding="utf-8")
    def copy_result(self):
        self.root.clipboard_clear();self.root.clipboard_append(self.result["output"]["text"])

def packaged_self_test():
    """Check the frozen app's parser, tokenizer, and optimizer without launching a GUI."""
    import tempfile
    import tiktoken
    if not (ROOT / "tiktoken_cache").is_dir():
        raise RuntimeError("Bundled offline tokenizer cache is missing")
    with tempfile.TemporaryDirectory() as folder:
        file = Path(folder) / "sample.txt"
        file.write_text("Order 1 shipped\nOrder 2 shipped\nOrder 1 shipped", encoding="utf-8")
        result = process([str(file)])
        if not hasattr(sys.modules["optimizer"], "_ENC"):
            raise RuntimeError("Bundled tiktoken encoding is missing")
        assert result["stats"]["lossless_verified"]
        assert result["output"]["text"]
        assert tiktoken.get_encoding("cl100k_base") is not None


if __name__=="__main__":
    if "--self-test" in sys.argv:
        packaged_self_test()
    else:
        app=tk.Tk();Desktop(app);app.mainloop()

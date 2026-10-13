# Contributing to TokenForge

Thanks for helping! The engine has to stay deterministic and lossless, so a few rules apply.

## Ground rules
1. **No LLM calls inside the engine.** `optimizer.py` and `parsers.py` must be pure algorithms.
2. **The round-trip must hold.** For any input, `reconstruct(records, map) == fragments`. Add a test to `backend/tests/test_engine.py` for any new behaviour.
3. **Never hide facts by default.** New folding strategies must respect the `facts` guard.

## Adding a file format
1. Write a parser in `backend/parsers.py` that returns `List[str]` fragments.
2. Register it in `_TEXT_PARSERS` (str input) or `_BYTE_PARSERS` (bytes input) with its kind (`prose | tabular | code | log`).
3. Optionally teach `_sniff_text_kind` to detect it when the extension is missing.
4. Add a sample to `samples/` and a test.

## Dev loop
```bash
cd backend && pytest tests/test_engine.py -q
python cli.py optimize ../samples/* -f annotated
```

## Pull requests
Keep PRs focused, describe the before and after token numbers on a sample, and include tests.

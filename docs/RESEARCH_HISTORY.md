# TokenForge R&D History — exact-evidence revision tracking

This is an **optional offline research workflow** for long-running technical
projects. It was designed for the problem of keeping past design changes
traceable over months or years, without silently merging away old conclusions.

It does **not** change the original TokenForge optimizer, its normal API,
token counts, budgets, near-duplicate engine, or existing output formats.

## Using the desktop application

1. Download the desktop release from GitHub Releases (not the source-code ZIP).
2. Launch TokenForge and click **R&D History**.
3. Add two or more document versions in the chronology **you** know is correct,
   oldest first. Use Move up / Move down to fix their order. Filenames and
   modification times are **not** treated as proof of chronology.
4. Select each version and choose **Explain change** to enter an optional,
   researcher-supplied reason, hypothesis, or evidence note. The tool copies
   that note verbatim; it never presents the note as independently verified.
5. Compare and inspect additions, removals and modifications with the
   **revision, document/ZIP member and fragment position** displayed.
6. Export **history TXT** for easy AI review and **evidence JSON** for a
   machine-readable audit trail.

A file's full original **SHA-256** fingerprint is recorded so future reviewers
can verify that the same file was examined. Neither your source files nor the
backing project data are changed or uploaded. The workflow needs no internet
connection, server, login or AI model.

## Exact matching versus scientific equivalence

* A repeated passage appears only once in the **exact repetition index** if the
  **extracted Unicode strings are identical**. Every original occurrence,
  including repeated instances inside the same version, is listed with its
  source location. The underlying chronological change list is never folded.
* `10 keV` and `10 MeV`, `8 MA` and `6 MA`, capitalization changes,
  added qualifiers, or different punctuation are **not** exact matches.
* Extracted-text equality is **not** original-file byte equality. Office/PDF
  parsers may remove styles, markup, whitespace, heading markers, graphics,
  equations rendered as pictures, embedded data or other features.
* If SHA-256 changes but extracted text is unchanged, the report flags
  **REVIEW REQUIRED**. It does not say the files are identical.
* Every sentence boundary is **not** automatically identified. A parser
  fragment can be a sentence, line, paragraph or table row. Exact passages
  are guaranteed to compare equal as strings **after extraction**, not to
  have identical meaning or original visual formatting.
* The tool does not determine which equation is correct, why a theory changed,
  whether an experiment succeeded, or which design is current. Only the user's
  ordering and notes provide those claims.
* Old assumptions are never marked "disproved" without explicit evidence
  from the researcher.

## Example

Input:
```
revision_01.txt: Current: 4 MA | Hold time: 150 microseconds
revision_02.txt: Current: 6 MA | Hold time: 30 microseconds
revision_03.txt: Current: 8 MA | Hold time: 10 microseconds
```

The timeline retains all three values and their version provenance. An
identical unchanged passage shared across files has one index entry pointing
to all its occurrences. The original inputs and change evidence remain intact.

## Supported files and limits

R&D history supports the **same extractable formats** as the desktop file
parser, including TXT, Markdown, PDF, DOCX, CSV, Excel and ZIP. This does **not**
mean scientific equations or images inside those files are fully captured.
The current initial implementation accepts **2–100 ordered files**, up to
**50 MB combined**, **12,000 extracted fragments per revision**, and
**30,000 change groups per version pair**. Use smaller batches for larger
projects. A large ZIP can contain several logical documents in one revision;
members are identified in the evidence output.

Both reports preserve the **full extracted change passages** and all referenced
version IDs. They do not silently shorten the report to fit AI token limits:
if the result is too large for an AI tool, split the version range into
overlapping batches and keep the exported JSON for audit.

## Data-handling precaution

This feature is for research you have permission to examine. It operates
locally and does **not** upload research material to the public TerranexTech
website or to GitHub. A public project description is not a substitute for
your private R&D records. Back up your original files, and verify sensitive
scientific statements directly against the source documents.

**Compatibility:** Normal `Optimize`, `Save TXT`, `Save recovery bundle`,
the web dashboard, CLI and API remain as before.

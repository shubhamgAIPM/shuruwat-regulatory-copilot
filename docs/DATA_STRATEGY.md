# Data Strategy

## Initial Corpus Audit

Audit date: 2026-09-06

The supplied source PDFs have been placed in `data/raw/`. No files were edited during relocation.

| File | Role | Size | PDF details | Initial extraction status |
| --- | --- | ---: | --- | --- |
| `Licensing_Regulations.pdf` | FSSAI licensing and registration source | 174,029 bytes | PDF 1.4; metadata reports 54 pages; deflate-compressed | Embedded PDF text structures are present, but text extraction has not yet been validated |
| `Labeling rules 1.pdf` | FSSAI labelling source | 2,369,584 bytes | PDF 1.6; metadata advertises 48 pages; deflate-compressed | Embedded PDF text structures are present, but text extraction has not yet been validated |
| `9 The Legal Metrology (Package Commodities) Rules, 2011.pdf` | Packaging and commodity declaration source | 136,603 bytes | PDF 1.5; deflate-compressed; PDF metadata advertises 43 pages | Embedded PDF text structures and image objects are present, but text extraction has not yet been validated |

SHA-256 fingerprints:

```text
4b1a009d4a7245c317dca2d79b49385b897faf90c0451cbb04ae924a86021a4  9 The Legal Metrology (Package Commodities) Rules, 2011.pdf
c23820b2952ca06ec22dca1cf7c14897441ffb2d290bd1940dd48b09a2f39b7a  Labeling rules 1.pdf
d8d11c6b79f9f0453b43f86b833b0dd9240adeeea7e3a4b22114b47e2d116612  Licensing_Regulations.pdf
```

## Findings

- The corpus is currently three documents at the repository boundary of the intended MVP.
- The licensing and labelling filenames appear aligned with the FSSAI registration and labelling scope.
- The Legal Metrology document may support packaging-label claims, but its overlap with the FSSAI corpus must be verified before it is treated as authoritative for an answer.
- Provenance, source URLs, publication dates, effective dates, versions, and amendment status have not been established from the filenames alone.
- The PDFs are not indexed as text by macOS. The files contain PDF text-related structures, so they may be text-based or may use encoded/scanned content that still requires a real PDF extraction test.
- The Legal Metrology file contains image objects in addition to text-related structures. Tables and image-backed pages must be checked during extraction.
- No OCR decision should be made until page-level extraction is tested with the selected parser.

## Extraction Validation Result

The first extraction run was completed with `pypdf` using `ingestion/inspect_pdfs.py`.

| File | Pages extracted | Pages with text | Empty pages | Extracted characters |
| --- | ---: | ---: | ---: | ---: |
| `Licensing_Regulations.pdf` | 54 | 54 | 0 | 179,024 |
| `Labeling rules 1.pdf` | 48 | 48 | 0 | 116,811 |
| `9 The Legal Metrology (Package Commodities) Rules, 2011.pdf` | 43 | 43 | 0 | 82,608 |

The pipeline preserved page numbers and wrote page-level inspection artifacts to `data/processed/`. Document metadata was available for all three files. Initial metadata identifies the Legal Metrology title and the licensing document as an FSSAI regulation source; the labelling document metadata does not include a title or authority.

The extraction result provides usable text on every page, so OCR is not currently required. This does not yet validate tables or the semantic accuracy of heading detection. The heading detector is deliberately preliminary and must be checked against representative pages before structure-aware chunking.

Representative-page review found a multilingual quality issue. The English portions of all three documents are readable, but both `pypdf` and PyMuPDF produce corrupted or legacy-font-mapped text in parts of the Hindi content, especially in `Labeling rules 1.pdf`. The presence of text on a page therefore does not prove that the extracted text is semantically reliable. The Legal Metrology document also contains form-like final pages where layout and table relationships need deliberate handling.

This creates a decision gate before chunking:

- If v1 answers are restricted to validated English text, mark language coverage explicitly in document metadata and exclude unvalidated Hindi passages.
- If Hindi questions and evidence are required, add a tested OCR or font-decoding path and manually validate representative pages before indexing them.

No multilingual regulatory claim should be indexed solely because its page has a non-zero character count.

## v1 Language Policy

For v1, Shuruwat will answer and index validated English content only. The raw PDFs and complete extraction artifacts remain preserved for audit purposes, but pages containing Devanagari text are marked `review_required` by the inspection pipeline and must not enter the vector index automatically. This avoids silently treating corrupted or unvalidated Hindi extraction as authoritative evidence.

The eventual chunking pipeline must carry the language eligibility field forward into chunk metadata and reject non-eligible pages. Hindi support can be added later through a separately validated OCR or font-decoding path without changing the document and chunk traceability model.

## Required Next Audit Gate

Before database or chunking design, install or select a reproducible PDF extraction tool and inspect every document page by page. The inspection must record:

- extracted character count by page
- pages with no usable text
- page-number preservation
- heading, section, subsection, and clause patterns
- table and image handling
- document title, authority, dates, version, and source URL
- extraction failures and whether OCR is required

The parser must preserve the original filename and a stable document fingerprint. It must emit traceable page-level processed artifacts before either chunking strategy is implemented.

## Scope and Provenance Risks

The Legal Metrology document is a separate authority from FSSAI. It must not silently expand the product into general legal or packaging advice. Any answer using it must be supported by explicit corpus metadata and the product scope must state how it relates to FSSAI labelling requirements.

Until provenance and extraction are validated, the documents are input candidates rather than an approved regulatory knowledge base.

## Repository Publication Decision

The project owner confirmed permission to publish the three supplied PDFs in the intended public GitHub repository. Their original filenames and SHA-256 fingerprints must remain unchanged so future users can verify corpus identity. No project license is currently declared; any future code license must not be interpreted as licensing the source documents.
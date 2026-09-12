# Raw ingestion specification

## Encoding and delimiter
The official resource pages describe the monitoring CSV files as UTF-8 with semicolon (`;`) delimiter.

## Expected schema
The parser expects the 24 source fields in `config/schema.csv`.

## Structural semicolon repair
A small number of raw rows contain an unescaped semicolon inside `Post_Name`. Because the remaining 22 columns have fixed positions, the parser repairs only the station-name portion by right-anchoring the final 22 fields and joining the split station-name fragments with a comma and space. The raw file remains unchanged; repair metadata are written separately.

## Missing values
Literal `NULL` is converted to an empty field in the curated CSV. Source numeric zero is preserved as zero.

## Spreadsheet date auto-conversion
Two source-published artefact classes are reconstructed:
- text patterns such as `15.Лип` -> `15.07` and `Лис.52` -> `11.52`;
- numeric Excel serial-date representations in hydrochemical fields when the decoded serial is structurally consistent with an auto-converted decimal.

The `Simazin` field is excluded from numeric serial inference, preventing the historical 2004–2006 large values from being silently reinterpreted as dates.

## Fail-closed behavior
Unexpected headers, unrepairable row lengths, duplicate record keys, unmatched candidate revisions or source fingerprint differences terminate the pipeline.

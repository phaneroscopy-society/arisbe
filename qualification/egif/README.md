# EGIF qualification

This directory contains a **bounded implementation qualification** for Arisbe's
EGIF and CGIF surfaces.

It is intentionally not an ISO/IEC 24707 conformance suite. EGIF is treated as
a separate linear notation for existential graphs; ISO/IEC 24707 remains the
authority for Common Logic and its standardized concrete dialects.

The qualification checks:

- positive and negative EGIF parsing;
- EGIF parse → generate → parse structural fixed points;
- a 10-case bidirectional EGIF ↔ CGIF slice through Arisbe's shared EGI;
- two falsification controls where the pinned CGIF grammar recognizes syntax
  but parse-tree → EGI conversion loses information.

The falsification controls are part of the acceptance contract. Parser
acceptance is not equivalent to faithful preservation.

Historical qualification source identity:
`c8c35eb43764fd204b72853e6d56737e053dd970`.
The repository moved from the original personal owner to
`phaneroscopy-society/arisbe`; the commit object is unchanged.

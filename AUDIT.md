# Audit — englishwords

Updated: 2026-09-15

The original entry point fails to compile because its nested loops exceed Python's static block limit. Its top-level execution also attempts every length from 1 through 26, materializes full lists and opens `words.txt` for replacement. The earlier generic audit did not detect these defects.

The repair uses a streaming iterator, an explicit maximum length, exact output estimates and independent word/byte limits. Existing output paths are refused. A same-directory temporary file preserves partial results on failure, and exclusive publication protects a destination created concurrently.

Local validation: 14 synthetic tests pass on Python 3.12. They cover 702 ordered one/two-letter entries, byte counts, a bounded-memory prefix of the 26-letter sequence, dry runs, workload limits, existing outputs, a publication race, interruption, unsupported publication and cleanup failure. The original source fails during test import with `SyntaxError: too many statically nested blocks`.

The new GitHub workflow verifies the same suite on Linux and Windows; repository checks must pass before release. No real word lists, database records, credentials, external providers or hosted services were opened or changed for validation. This repair reduces local generation memory use; it is not a Vercel CPU or monthly quota measurement.

"""Stream lowercase letter combinations with explicit workload and output bounds."""
from __future__ import annotations

import argparse
from itertools import product
import os
from pathlib import Path
import string
import sys
import tempfile
from typing import Iterator

ALPHABET = string.ascii_lowercase
DEFAULT_MAX_WORDS = 1_000_000
DEFAULT_MAX_BYTES = 100_000_000


def _validate_range(min_length: int, max_length: int) -> None:
    if (type(min_length) is not int or type(max_length) is not int
            or not 1 <= min_length <= max_length <= 26):
        raise ValueError("Lengths must be integers with 1 <= min <= max <= 26")


def estimate_output(min_length: int, max_length: int) -> tuple[int, int]:
    """Return the exact line count and ASCII/LF byte count without generating."""
    _validate_range(min_length, max_length)
    counts = [(length, len(ALPHABET) ** length)
              for length in range(min_length, max_length + 1)]
    return sum(count for _, count in counts), sum((length + 1) * count for length, count in counts)


def iter_words(min_length: int, max_length: int) -> Iterator[str]:
    """Yield combinations in the original length-first, alphabetical order."""
    _validate_range(min_length, max_length)
    return ("".join(letters)
            for length in range(min_length, max_length + 1)
            for letters in product(ALPHABET, repeat=length))


def write_words(output: Path, min_length: int, max_length: int, *,
                max_words: int = DEFAULT_MAX_WORDS,
                max_bytes: int = DEFAULT_MAX_BYTES) -> tuple[int, int]:
    """Publish a complete file exclusively; preserve originals and failed attempts."""
    count, size = estimate_output(min_length, max_length)
    if type(max_words) is not int or type(max_bytes) is not int or min(max_words, max_bytes) < 1:
        raise ValueError("Word and byte limits must be positive integers")
    if count > max_words or size > max_bytes:
        raise ValueError(f"Requested {count:,} words / {size:,} bytes exceeds limits "
                         f"of {max_words:,} words / {max_bytes:,} bytes; "
                         "choose shorter lengths or explicitly raise both applicable limits")
    destination = Path(output).absolute()
    if os.path.lexists(destination):
        raise FileExistsError(f"Output already exists; choose a new path: {destination}")

    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="ascii", newline="\n",
                                         dir=destination.parent, prefix=f".{destination.name}.",
                                         suffix=".partial", delete=False) as handle:
            temporary = Path(handle.name)
            for word in iter_words(min_length, max_length):
                handle.write(word + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        # Same-directory linking publishes only if the destination is still absent.
        # A precheck followed by replace/rename could overwrite a concurrent file.
        os.link(temporary, destination)
    except BaseException as error:
        if temporary is not None:
            error.add_note(f"Generated data retained for inspection at {temporary}")
        raise
    try:
        temporary.unlink()
    except OSError:
        print(f"Output is complete; duplicate partial file remains at {temporary}", file=sys.stderr)
    return count, size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-length", type=int, default=1)
    parser.add_argument("--max-length", type=int, required=True)
    parser.add_argument("--max-words", type=int, default=DEFAULT_MAX_WORDS)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--output", type=Path, default=Path("words.txt"))
    parser.add_argument("--dry-run", action="store_true", help="Print exact output totals without writing")
    args = parser.parse_args(argv)
    try:
        count, size = estimate_output(args.min_length, args.max_length)
        print(f"{count:,} words; {size:,} bytes (ASCII with LF newlines)")
        if args.dry_run:
            return 0
        write_words(args.output, args.min_length, args.max_length,
                    max_words=args.max_words, max_bytes=args.max_bytes)
        print(f"Complete: {args.output}")
        return 0
    except (OSError, ValueError, KeyboardInterrupt) as error:
        print("Interrupted" if isinstance(error, KeyboardInterrupt) else str(error), file=sys.stderr)
        for note in getattr(error, "__notes__", []):
            print(note, file=sys.stderr)
        return 130 if isinstance(error, KeyboardInterrupt) else 1


if __name__ == "__main__":
    raise SystemExit(main())

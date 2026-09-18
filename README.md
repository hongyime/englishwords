# englishwords

**Live:** https://hongyime.github.io/englishwords/

![screenshot](./screenshot.png)
Generate lowercase letter combinations, including gibberish, in alphabetical order within each word length. Python 3.11 or newer is required; there are no third-party dependencies.

## Usage

Choose the maximum length explicitly. Preview the exact line count and output size first:

```sh
python englishwords.py --max-length 4 --dry-run
python englishwords.py --max-length 3
```

The second command writes lengths 1 through 3 to `words.txt` (18,278 lines). To generate just one length or use another output path:

```sh
python englishwords.py --min-length 2 --max-length 2 --output two-letter-words.txt
```

Defaults allow at most 1,000,000 words and 100,000,000 output bytes. Requests exceeding either limit stop before creating a file. To permit a larger run, explicitly raise the applicable limits:

```sh
python englishwords.py --max-length 5 --dry-run
python englishwords.py --max-length 5 --max-words 13000000 --max-bytes 80000000
```

Limits control the complete requested output; they do not truncate the word list. Lengths range from 1 through 26. The count grows exponentially as 26 raised to the word length, so streaming reduces memory use without making enormous lists practical. Output is ASCII with LF newlines, and byte estimates include those newlines. Importing the module performs no generation or file access.

## Output preservation

An existing output path is never overwritten. Choose a new filename to generate another list. Data is streamed to a unique `.partial` file in the output directory and published only after generation completes. Publication also refuses a destination created by another process during generation.

Interrupted or failed attempts retain their partial file and print its location for inspection. A filesystem that cannot create hard links leaves the complete partial file available and reports an error; it does not fall back to overwriting a destination. If cleanup fails after publication, the completed output and duplicate partial file are both retained and a warning identifies the duplicate.

## Development

```sh
python -m unittest discover -s tests -v
```

Tests use temporary fixtures and cover ordering, exact sizing, bounded memory, workload limits, import behavior, interrupted writes and concurrent output preservation. GitHub Actions runs the same checks on Linux and Windows.

This is a local command-line utility. No Supabase or Vercel service is required.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

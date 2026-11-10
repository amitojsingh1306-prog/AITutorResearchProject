# Local OCR for the tutor

Status: downloaded and available as a standalone component. The existing chat
routes, frontend, memory retrieval and dependency versions are unchanged.

## Engine and model

- Engine: Tesseract 5.5.2, already installed on this Mac.
- Weights: official `tessdata_best/eng.traineddata`, approximately 15 MB.
- Neural recognizer: LSTM, explicitly selected with `--oem 1`.
- License: Apache-2.0, copied beside the weights.
- Exact source commit and SHA-256: `ocr_models/tessdata_best/model.json`.
- Runtime dependencies: Python standard library and the Tesseract executable.

Tesseract describes tessdata_best as its accuracy-oriented model family, trading
speed for recognition quality. This does not guarantee perfect extraction.
Source: https://tesseract-ocr.github.io/tessdoc/Data-Files.html

## Run

From this project folder:

```bash
python3 scripts/ocr_image.py "/absolute/path/to/image.png" --output ocr_outputs/result.json
```

For a single text block, add `--psm 6`. For scattered labels, try `--psm 11`.
The default, `--psm 3`, uses automatic page segmentation.

To also ask the existing text-only Qwen model about the extracted text:

```bash
python3 scripts/ocr_image.py "/absolute/path/to/image.png" \
  --question "Explain the text extracted from this image." \
  --output ocr_outputs/result.json
```

The optional Qwen step requires LM Studio's local server on port 1234 and the
specified Qwen model loaded. Use `--model` if its identifier differs. OCR-only
execution makes no network request. The optional Qwen call uses loopback only,
ignores proxy configuration and never changes saved conversations.

## Output and limits

The JSON contains original extracted text, per-word coordinates and OCR scores,
extraction time, model checksum, and an optional Qwen answer. OCR scores are not
probabilities that a claim is true. The timer covers the Tesseract extraction,
not a Qwen response. No automatic Chroma indexing occurs.

This first component reads printed English text from images. It does not
interpret objects, arrows, graph relationships or engineering diagrams, and it
does not reliably transcribe handwriting or mathematical notation. Preserve the
image and review critical symbols, numbers, dates and equations. Future visual
understanding needs a separate vision model and validation.

Images must be local PNG, JPEG, TIFF, BMP or WebP files, at most 25 MiB. PDF input
is not implemented. Long extracted text must be narrowed before the optional
Qwen demo call. The text is untrusted evidence, not executable instructions;
prompt separation helps but does not guarantee immunity to prompt injection.

This component is included in the consolidated `/Users/amitoj/Developer/AITutor`
project. It remains a separate command and is not connected to the chat server.

## Restore the model on another machine

Install Tesseract, download the source URL in `model.json` to this directory as
`eng.traineddata`, and confirm the recorded SHA-256 before use. Recognition does
not need network access after this one-time download. The weight file is excluded
from git; the manifest and upstream license describe the reproducible source.

## Tests

```bash
python3 -m unittest backend.tests.test_local_ocr -v
```

The tests include installed-weight integrity and therefore require the downloaded
model. Real-image extraction must also be checked; unit tests alone do not prove
OCR accuracy on arbitrary documents.

## Verified on this Mac

On 7 November 2026, all nine unit tests passed. Real extraction also completed on
the original binary-search recall screenshot recovered from the presentation:
62 words in approximately one second. It retained "Python Binary Search" and
"short explanations using numbered steps", but read the standalone "I" in the
question as a vertical bar. This is an observed limitation, not perfect OCR.

A database slide took approximately 0.9 seconds and extracted its larger text,
but some small screenshot text was missing or garbled. These are individual
checks, not an accuracy benchmark. Reports and the recall image are under
`ocr_outputs/`. LM Studio was not listening on the local model port during this
setup, so generation by Qwen was not verified in this run.

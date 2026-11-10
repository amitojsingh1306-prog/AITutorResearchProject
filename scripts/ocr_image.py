"""Extract image text locally; optionally ask local Qwen about the extracted text."""

import argparse
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.ocr.local_ocr import LocalOCR, OCRError, qwen_messages
from backend.ocr.image_memory import DEFAULT_MEMORY_DIRECTORY, save_image_memory, write_record, update_image_memory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--psm", type=int, choices=[3, 6, 11], default=3)
    parser.add_argument("--output", type=Path, help="Also export the common JSON record here.")
    parser.add_argument("--memory-dir", type=Path, default=DEFAULT_MEMORY_DIRECTORY,
                        help="Local folder for image copies and JSON records.")
    parser.add_argument("--user-id", default="local-user")
    parser.add_argument("--chat-id", default=None)
    parser.add_argument("--question", help="Optional question for local Qwen; OCR alone is the default.")
    parser.add_argument("--model", default="qwen2.5-1.5b-instruct")
    args = parser.parse_args()
    try:
        result = LocalOCR().extract(args.image, args.psm)
        record_path, payload = save_image_memory(
            args.image, result, directory=args.memory_dir, user_id=args.user_id,
            chat_id=args.chat_id, question=args.question)
        print(result.text or "No readable text found.")
        print(f"\nOCR: {len(result.words)} words, {result.elapsed_ms:.2f} ms")
        print(f"Saved image memory: {record_path}")
        if args.question:
            body = dict(model=args.model, messages=qwen_messages(result, args.question),
                        temperature=0.1, max_tokens=256, stream=False)
            request = urllib.request.Request(
                "http://127.0.0.1:1234/v1/chat/completions",
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            # Bypass proxy settings to keep this request on the local machine.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            try:
                with opener.open(request, timeout=120) as response:
                    answer = json.load(response)["choices"][0]["message"]["content"]
                payload['generation'].update(model=args.model, answer=answer, status='completed')
                print("\nQwen:\n" + answer)
            except (urllib.error.URLError, TimeoutError) as error:
                payload['generation'].update(model=args.model, error=str(error), status='failed')
                print("\nOCR succeeded, but local Qwen is unavailable. Start LM Studio's server.",
                      file=sys.stderr)
        update_image_memory(record_path, payload)
        if args.output:
            write_record(args.output.expanduser(), json.loads(record_path.read_text()))
        if payload['generation']['status'] == 'failed':
            return 2
    except (OCRError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

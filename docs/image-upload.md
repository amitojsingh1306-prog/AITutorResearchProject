# Images in chat

Use the image button beside the message field, select a PNG/JPEG/WebP/BMP/TIFF
up to 25 MiB, optionally type a question, and send. The selected image has a
preview and can be removed before sending. Sending an image without a question
asks the tutor to explain its readable text.

The browser sends image bytes to the local FastAPI server. Local Tesseract reads
them; the server saves the image and OCR in the conversation's common session
record. The normal streamed Qwen response receives a bounded, quoted OCR excerpt
(up to 1,000 UTF-8 bytes), not image pixels. The full OCR stays in the session
record. Long images should be cropped to the relevant text. This is text-reading
support, not object/diagram recognition or a vision-model upgrade.

Uploaded evidence is associated with user and chat IDs. The message stores an
attachment reference and searchable OCR excerpt; Nomic indexes the excerpt with
the message in Chroma. The common image entry also records the question/answer.
Image retrieval verifies user/chat ownership and uses non-cached responses.
The frontend reloads the saved thumbnail and exposes extracted text separately.
Unreadable images, unsupported formats, empty files and oversized uploads show
an error. No external image or OCR service is used.

Uploads participate in the existing one-hour idle session policy. The backend
removes owned copies and associated indexes when the session expires. Originals
on the user's computer, exports and backups are outside that cleanup scope.

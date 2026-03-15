def split_text_into_chunks(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
  text = text.strip()
  if not text:
      return []

  chunks = []
  start = 0
  text_len = len(text)

  while start < text_len:
    end = min(start + chunk_size, text_len)
    chunk = text[start:end].strip()
    if chunk:
      chunks.append(chunk)

    if end >= text_len:
      break

    start = max(end - overlap, 0)

  return chunks
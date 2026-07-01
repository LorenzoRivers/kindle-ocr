#!/usr/bin/env python3
"""Trascrive PDF manoscritti (es. Kindle Scribe) in testo pulito usando Claude vision."""

import argparse
import base64
import sys
import time
from pathlib import Path

import anthropic
import fitz  # pymupdf

MODEL = "claude-sonnet-5"
DPI = 150
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # secondi, raddoppia ad ogni tentativo

TRANSCRIPTION_PROMPT = """Sei un trascrittore esperto di testo manoscritto in italiano.
Trascrivi esattamente il testo scritto a mano in questa immagine.
Mantieni la struttura (titoli, elenchi, frecce, simboli se presenti).
Non aggiungere nulla che non sia scritto. Non correggere o interpretare, trascrivi fedelmente.
Rispondi solo con il testo trascritto, senza preamboli."""


def parse_page_range(spec: str, total_pages: int) -> list[int]:
    """Converte 'N' o 'N-M' (1-indexed, inclusivo) in una lista di indici 0-indexed."""
    if "-" in spec:
        start_s, end_s = spec.split("-", 1)
        start, end = int(start_s), int(end_s)
    else:
        start = end = int(spec)

    if start < 1 or end > total_pages or start > end:
        raise ValueError(
            f"Range di pagine non valido: {spec!r} (il PDF ha {total_pages} pagine)"
        )
    return list(range(start - 1, end))


def page_to_base64_png(page: fitz.Page) -> str:
    pix = page.get_pixmap(dpi=DPI)
    return base64.b64encode(pix.tobytes("png")).decode()


def transcribe_page(client: anthropic.Anthropic, image_b64: str, page_num: int) -> str:
    """Chiama Claude per trascrivere una pagina, con retry su errori transienti."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=2000,
                thinking={"type": "disabled"},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_b64,
                                },
                            },
                            {"type": "text", "text": TRANSCRIPTION_PROMPT},
                        ],
                    }
                ],
            )
            text_block = next(
                (b for b in response.content if b.type == "text"), None
            )
            return text_block.text if text_block else ""
        except (anthropic.RateLimitError, anthropic.InternalServerError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(
                    f"  [pagina {page_num}] errore transiente ({e.__class__.__name__}), "
                    f"retry {attempt}/{MAX_RETRIES} tra {delay}s...",
                    file=sys.stderr,
                )
                time.sleep(delay)
        except anthropic.APIError as e:
            # Errore non recuperabile (es. richiesta malformata) - non ritentare
            last_error = e
            break

    raise RuntimeError(
        f"Trascrizione della pagina {page_num} fallita dopo {MAX_RETRIES} tentativi: {last_error}"
    )


def transcribe_pdf(pdf_path: Path, pages_spec: str | None) -> str:
    doc = fitz.open(pdf_path)
    client = anthropic.Anthropic()

    if pages_spec:
        page_indices = parse_page_range(pages_spec, doc.page_count)
    else:
        page_indices = list(range(doc.page_count))

    results = []
    total = len(page_indices)
    for i, page_index in enumerate(page_indices, start=1):
        page_num = page_index + 1
        print(f"Trascrizione pagina {page_num} ({i}/{total})...")
        page = doc[page_index]
        image_b64 = page_to_base64_png(page)
        try:
            text = transcribe_page(client, image_b64, page_num)
            results.append(f"## Pagina {page_num}\n\n{text}")
        except RuntimeError as e:
            print(f"  ATTENZIONE: {e}", file=sys.stderr)
            results.append(f"## Pagina {page_num}\n\n[ERRORE: trascrizione fallita - {e}]")

    doc.close()
    return "\n\n---\n\n".join(results)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trascrive un PDF manoscritto (Kindle Scribe) in Markdown usando Claude vision."
    )
    parser.add_argument("pdf_path", type=Path, help="Percorso del PDF da trascrivere")
    parser.add_argument(
        "--pages",
        type=str,
        default=None,
        help="Intervallo di pagine da trascrivere, 1-indexed (es. '3' o '1-3'). Default: tutte.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Percorso del file .md di output. Default: [nome_pdf]_trascritto.md nella stessa cartella del PDF.",
    )
    args = parser.parse_args()

    if not args.pdf_path.is_file():
        print(f"Errore: file non trovato: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    output_path = args.output or args.pdf_path.with_name(
        f"{args.pdf_path.stem}_trascritto.md"
    )

    try:
        markdown = transcribe_pdf(args.pdf_path, args.pages)
    except ValueError as e:
        print(f"Errore: {e}", file=sys.stderr)
        sys.exit(1)

    output_path.write_text(markdown, encoding="utf-8")
    print(f"\nFatto. Trascrizione salvata in: {output_path}")


if __name__ == "__main__":
    main()

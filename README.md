# kindle-ocr

Script per trascrivere in italiano i PDF di appunti manoscritti (es. Kindle Scribe) usando la vision di Claude, dato che l'OCR nativo del Kindle produce output inutilizzabile su corsivo italiano.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."   # oppure aggiungila a ~/.zshrc per renderla permanente
```

## Uso

```bash
python ocr.py percorso/al/file.pdf
```

Genera `percorso/al/file_trascritto.md` nella stessa cartella del PDF, con ogni pagina sotto un'intestazione `## Pagina N`.

### Opzioni

- `--pages N` oppure `--pages N-M`: trascrive solo un sottoinsieme di pagine (1-indexed, inclusivo). Utile per fare un test veloce su 1-2 pagine prima di lanciare l'intero PDF.
- `--output percorso/file.md`: cambia il percorso/nome del file di output.

Esempi:

```bash
python ocr.py note.pdf --pages 1-3
python ocr.py note.pdf --output ~/Desktop/note_pulite.md
```

## Note

- Modello usato: `claude-sonnet-5`, con thinking disattivato (non serve ragionamento per una trascrizione fedele, solo lettura dell'immagine) — mantiene i costi bassi.
- Costo stimato: circa 2-3 centesimi ogni 10 pagine.
- In caso di errori transienti dell'API (rate limit, errori server) lo script ritenta automaticamente fino a 3 volte con backoff esponenziale. Se una pagina fallisce definitivamente, viene segnalata nel Markdown finale ma la trascrizione delle altre pagine prosegue.

# media/ — Media & Uploaded Files

User-uploaded files and media assets served by Django.

## Structure

```
media/
└── data_source/    # Uploaded PDF files (default upload target)
```

## Notes

- `media/data_source/` is the `DOCUMENTS_PATH` from settings
- PDFs uploaded via `/api/upload/` are saved here
- This directory is auto-created by `app.config.get_settings()`

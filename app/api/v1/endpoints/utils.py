# filepath: app/api/v1/endpoints/utils.py
from typing import Optional, List
from pyresparser import ResumeParser  # type: ignore
import os
import tempfile
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

router = APIRouter(prefix="/utils", tags=["utils"])


@router.post(
    "/convert",
    summary="Convert an uploaded file to a desired format",
)
async def convert_file(
    to_format: str = Form(...),
    file: UploadFile = File(..., description="Source file to convert"),
    from_format: Optional[str] = Form(None),
):
    """
    Stub endpoint for generic file conversion. The implementation should:
    - Detect `from_format` if not provided
    - Convert content to `to_format`
    - Return converted bytes as a file response with correct content-type and filename
    """
    # TODO: Implement actual file conversion logic
    raise HTTPException(status_code=501, detail="convert_file not implemented yet")


@router.post("/parse-resumes", summary="Parse multiple uploaded resume PDFs")
async def parse_resumes(files: List[UploadFile] = File(..., description="One or more PDF resume files")):
    """Convert the provided Django view to FastAPI.

    Django original (concept):
    for pdf_name in request.data:
        pdf_data = request.data[pdf_name]
        file = pdf_data.open()
        write file, then ResumeParser(...).get_extracted_data()

    FastAPI version:
    - Accept multiple files via 'files' field.
    - Validate each is a PDF.
    - Persist temporarily and run ResumeParser if available.
    - Aggregate results and return {"data": [...]}.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    import nltk
    nltk.download('stopwords')


    results = []
    for upload in files:
        if upload.content_type not in ("application/pdf", "application/x-pdf"):
            raise HTTPException(status_code=400, detail=f"Unsupported content type: {upload.content_type}")
        # Create a named temp file to satisfy ResumeParser (expects a file path)
        suffix = ".pdf" if not upload.filename or not upload.filename.lower().endswith(".pdf") else ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file_bytes = await upload.read()
            tmp.write(file_bytes)
            tmp_path = tmp.name
        try:
            parsed = ResumeParser(tmp_path).get_extracted_data()
        except Exception as e:
            # Clean up file before raising
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise HTTPException(status_code=500, detail=f"Failed to parse {upload.filename}: {e}")
        # Clean up temp file
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        results.append({
            "filename": upload.filename,
            "data": parsed,
        })

    return {"data": results}

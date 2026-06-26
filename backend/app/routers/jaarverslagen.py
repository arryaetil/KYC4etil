import fitz  # PyMuPDF
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import JaarverslagUpload

router = APIRouter(prefix="/jaarverslagen", tags=["jaarverslagen"])


@router.post("/upload")
async def upload_jaarverslag(
    file: UploadFile,
    company_id: str | None = Form(None),
    jaar: int | None = Form(None),
    db: Session = Depends(get_db),
):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Bestand moet een PDF zijn (.pdf)")

    content = await file.read()
    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception:
        raise HTTPException(status_code=422, detail="Ongeldig PDF-bestand")

    tekst = "\n\n".join(page.get_text() for page in doc)
    paginas = len(doc)
    doc.close()
    if not tekst.strip():
        raise HTTPException(status_code=422, detail="PDF bevat geen leesbare tekst (mogelijk een scan)")

    upload = JaarverslagUpload(
        company_id=company_id,
        bestandsnaam=file.filename,
        pdf_tekst=tekst,
        jaar=jaar,
    )
    db.add(upload)
    db.commit()
    return {"upload_id": upload.id, "bestandsnaam": upload.bestandsnaam, "paginas": paginas}

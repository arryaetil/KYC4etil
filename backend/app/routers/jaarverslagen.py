import fitz  # PyMuPDF
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import JaarverslagUpload, JaarverslagChatMessage

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


@router.get("")
def lijst_uploads(company_id: str | None = None, db: Session = Depends(get_db)):
    query = db.query(JaarverslagUpload)
    if company_id:
        query = query.filter_by(company_id=company_id)
    return [
        {
            "upload_id": u.id,
            "bestandsnaam": u.bestandsnaam,
            "jaar": u.jaar,
            "company_id": u.company_id,
            "uploaded_at": u.uploaded_at.isoformat(),
            "aantal_berichten": len(u.berichten),
        }
        for u in query.all()
    ]


@router.get("/{upload_id}")
def detail_upload(upload_id: str, db: Session = Depends(get_db)):
    upload = db.get(JaarverslagUpload, upload_id)
    if not upload:
        raise HTTPException(404, "Upload niet gevonden")
    return {
        "upload": {
            "upload_id": upload.id,
            "bestandsnaam": upload.bestandsnaam,
            "jaar": upload.jaar,
            "company_id": upload.company_id,
            "uploaded_at": upload.uploaded_at.isoformat(),
        },
        "berichten": [
            {"rol": b.rol, "inhoud": b.inhoud, "created_at": b.created_at.isoformat()}
            for b in upload.berichten
        ],
    }

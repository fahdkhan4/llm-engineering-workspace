from fastapi import APIRouter

router = APIRouter()

@router.post("/")
def _extract_document_details():
    return None


@router.get("/")
def _ask_questions():
    return {"question":"Ask Questions"}
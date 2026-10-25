from io import BytesIO
from pathlib import Path
import uuid
import warnings

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

from app.security import require_admin
from app.settings import settings

router = APIRouter(prefix="/api/admin/media", tags=["admin media"])
MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
Image.MAX_IMAGE_PIXELS = 30_000_000


@router.post("/images", status_code=status.HTTP_201_CREATED)
async def upload_course_image(file: UploadFile, _: object = Depends(require_admin)) -> dict:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP image")
    raw = await file.read(MAX_IMAGE_BYTES + 1)
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 8 MB upload limit")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            source = Image.open(BytesIO(raw))
            if getattr(source, "is_animated", False):
                raise HTTPException(status_code=415, detail="Animated images are not supported")
            source.verify()
            source = Image.open(BytesIO(raw))
            source = ImageOps.exif_transpose(source)
            if source.width * source.height > Image.MAX_IMAGE_PIXELS:
                raise HTTPException(status_code=413, detail="Image dimensions are too large")
            converted = source.convert("RGBA" if "A" in source.getbands() else "RGB")
            encoded = BytesIO()
            converted.save(encoded, format="WEBP", quality=86, method=6)
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(status_code=415, detail="The uploaded file is not a supported, valid image")

    filename = f"{uuid.uuid4().hex}.webp"
    upload_dir: Path = settings.media_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / filename).write_bytes(encoded.getvalue())
    return {"url": f"/uploads/{filename}", "content_type": "image/webp"}

"""Misc utility endpoints: resume parser (public) + image upload (auth)."""
import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from es.carousels.adapters import ImageKitStorage
from es.config import get_settings
from es.parser_impl import ResumeParser
from fastapp.auth import Principal, require_principal

router = APIRouter(tags=["misc"])


@router.post("/parser")
async def parse_resumes(files: list[UploadFile]):
	if not files:
		raise HTTPException(status.HTTP_400_BAD_REQUEST, "No file uploaded. Send multipart 'files'.")
	results = []
	for upload in files:
		fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
		try:
			with os.fdopen(fd, "wb") as f:
				f.write(await upload.read())
			results.append({"name": upload.filename, "data": ResumeParser(tmp_path).get_extracted_data()})
		finally:
			try:
				os.unlink(tmp_path)
			except OSError:
				pass
	return {"results": results}


@router.post("/images")
async def upload_image(file: UploadFile, principal: Principal = Depends(require_principal)):
	if not file or not file.filename:
		raise HTTPException(status.HTTP_400_BAD_REQUEST, "file required")
	data = await file.read()
	try:
		url, fid = ImageKitStorage(get_settings()).upload(data, filename=file.filename, folder="/uploads")
	except Exception as exc:
		raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
	return {"url": url, "id": fid}

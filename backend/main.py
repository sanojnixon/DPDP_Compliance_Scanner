import os
import base64
import logging
import asyncio
import traceback
import threading
import re
from functools import partial
from contextlib import asynccontextmanager
from typing import List
import uuid

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncpg
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv
from PIL import Image
import io
from pii_rules import generate_compliance_report
from dpdp_rules_engine import evaluate_dpdp_compliance
from document_classifier import classify_document
from ai_reasoning import analyze_dpdp_compliance, analyze_entity_candidates
from ocr_structure import parse_ocr_structure
from ai_providers import get_provider_diagnostics
from layout_mapping import build_layout_debug
from ocr_debug import render_ocr_debug_overlay
from candidate_generator import generate_entity_candidates
from entity_resolution import resolve_entities
from services.ai_service import run_text_analysis, HF_TEXT_MODEL
from ropa_generator import generate_ropa_entry, generate_personal_data_inventory
from ropa_export import export_ropa_xlsx

from fastapi import BackgroundTasks
import os, base64
from apk_jobs import create_job, get_job, update_job
from apk_static_analyzer import analyze_apk
from apk_navigator import navigate_and_capture

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/dpdp")
JWT_SECRET = os.getenv("JWT_SECRET", "supersecret_dpdp_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Global DB pool
pool = None

# ── EasyOCR lazy singleton ──
_ocr_engine = None
import threading
ocr_lock = threading.Lock()

def get_ocr_engine():
    """Initialise EasyOCR once and reuse the instance."""
    global _ocr_engine
    if _ocr_engine is None:
        try:
            import easyocr
            logger.info(f"Initialising EasyOCR engine v{easyocr.__version__} ...")
            # gpu=False ensures CPU-only mode inside Docker (no CUDA required)
            # Added 'hi' (Hindi) to natively support the Indian Rupee symbol (₹) and avoid '3' or '7' misclassifications
            _ocr_engine = easyocr.Reader(['en', 'hi'], gpu=False, verbose=False)
            logger.info("EasyOCR engine ready.")
        except Exception as e:
            logger.error(f"EasyOCR init FAILED: {e}\n{traceback.format_exc()}")
            raise
    return _ocr_engine

async def cleanup_old_images():
    """Background task to delete images older than 15 minutes."""
    while True:
        try:
            await asyncio.sleep(300) # Run every 5 minutes
            if pool:
                async with pool.acquire() as conn:
                    # Delete records older than 15 minutes
                    result = await conn.execute(
                        "DELETE FROM images WHERE uploaded_at < NOW() - INTERVAL '15 minutes'"
                    )
                    deleted_count = int(result.split(" ")[-1]) if result.startswith("DELETE") else 0
                    if deleted_count > 0:
                        logger.info(f"Cleanup: Deleted {deleted_count} abandoned images.")
        except asyncio.CancelledError:
            logger.info("Cleanup task cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in cleanup_old_images task: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    logger.info("Connecting to database...")
    pool = await asyncpg.create_pool(dsn=DATABASE_URL)
    
    # Init DB schema
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(100) NOT NULL,
                original_name VARCHAR(255) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                image_data TEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS dev_baselines (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(100) NOT NULL,
                file_name VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                payload JSONB NOT NULL
            );
        """)
        # Sync initial users
        initial_users = [
            {'userId': 'E1001', 'password': 'Password123!'},
            {'userId': 'E1002', 'password': 'Password123!'},
            {'userId': 'E1003', 'password': 'Password123!'},
            {'userId': 'sanoj', 'password': 'sib123'},
            {'userId': 'admin', 'password': 'admin'}
        ]
        for u in initial_users:
            hashed = pwd_context.hash(u['password'])
            await conn.execute("""
                INSERT INTO users (user_id, password_hash) 
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET password_hash = EXCLUDED.password_hash
            """, u['userId'], hashed)
        logger.info("Synced initial users.")
    
    # Start the background cleanup task
    cleanup_task = asyncio.create_task(cleanup_old_images())
    
    yield
    
    # Cancel the background cleanup task on shutdown
    cleanup_task.cancel()
    
    logger.info("Closing database connection...")
    await pool.close()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    userId: str
    password: str

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)

async def get_current_user(request: Request):
    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    token = token.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id: str = payload.get("userId")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=403, detail="Could not validate credentials")

@app.post("/api/login")
async def login(req: LoginRequest):
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", req.userId)
        if not user or not pwd_context.verify(req.password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid User ID or password")
        
        access_token = create_access_token(
            data={"userId": user['user_id']},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return {"message": "Login successful", "token": access_token}

@app.post("/api/upload")
async def upload_images(images: List[UploadFile] = File(...), user_id: str = Depends(get_current_user)):
    if not images:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    
    image_ids = []
    async with pool.acquire() as conn:
        async with conn.transaction():
            for file in images:
                content = await file.read()
                b64_data = base64.b64encode(content).decode('utf-8')
                mime_type = file.content_type or "image/jpeg"
                data_uri = f"data:{mime_type};base64,{b64_data}"
                
                filename = f"{file.filename.split('.')[0]}_{int(datetime.utcnow().timestamp())}.{file.filename.split('.')[-1]}"
                
                inserted_id = await conn.fetchval(
                    "INSERT INTO images (user_id, original_name, filename, image_data) VALUES ($1, $2, $3, $4) RETURNING id",
                    user_id, file.filename, filename, data_uri
                )
                image_ids.append(inserted_id)
    return {"message": f"Successfully uploaded {len(images)} images.", "image_ids": image_ids}

@app.get("/api/images")
async def get_images(ids: str = None, user_id: str = Depends(get_current_user)):
    async with pool.acquire() as conn:
        if ids:
            id_list = [int(i) for i in ids.split(",")]
            records = await conn.fetch(
                "SELECT id, original_name, image_data, uploaded_at FROM images WHERE user_id = $1 AND id = ANY($2) ORDER BY uploaded_at DESC",
                user_id, id_list
            )
        else:
            records = await conn.fetch(
                "SELECT id, original_name, image_data, uploaded_at FROM images WHERE user_id = $1 ORDER BY uploaded_at DESC",
                user_id
            )
        return [
            {
                "id": r["id"],
                "name": r["original_name"],
                "data": r["image_data"],
                "uploaded_at": r["uploaded_at"].isoformat()
            }
            for r in records
        ]

@app.delete("/api/images/{image_id}")
async def delete_image(image_id: int, user_id: str = Depends(get_current_user)):
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM images WHERE id = $1 AND user_id = $2", image_id, user_id
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Image not found or unauthorized")
        return {"message": "Image deleted successfully"}


def _run_ocr_sync(image_bytes: bytes) -> list:
    """
    Run EasyOCR synchronously in a thread pool.
    EasyOCR returns: [ [bbox, text, confidence], ... ]
    where bbox = [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
    """
    with ocr_lock:
        logger.info(f"[OCR] Acquired lock. Starting OCR on image ({len(image_bytes)} bytes)")
        engine = get_ocr_engine()
        try:
            import numpy as np
            # Decode bytes -> numpy RGB array (EasyOCR accepts numpy arrays directly)
            img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            img_np = np.array(img)
            logger.info(f"[OCR] Image decoded: size={img.size}, mode={img.mode}")
            result = engine.readtext(img_np, detail=1)
            logger.info(f"[OCR] Raw result: {len(result)} entries")
            return result or []
        except Exception as e:
            logger.error(f"[OCR] Exception in _run_ocr_sync: {e}\n{traceback.format_exc()}")
            raise


def _parse_ocr_result(raw_results: list) -> list:
    """
    Normalise EasyOCR output to a flat list of block dicts.
    EasyOCR readtext(detail=1) returns:
      [ [bbox, text, confidence], ... ]
    where bbox = [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
    """
    hindi_to_ascii = str.maketrans('०१२३४५६७८९', '0123456789')
    blocks = []
    if not raw_results:
        return blocks
    for item in raw_results:
        try:
            if not item or len(item) < 3:
                continue
            bbox, text, confidence = item[0], item[1], item[2]
            # Normalise bbox to list of [x, y] pairs
            norm_bbox = [[round(float(pt[0]), 1), round(float(pt[1]), 1)] for pt in bbox]
            text_str = str(text).translate(hindi_to_ascii)
            text_str = re.sub(r'(?:^|\s)(?:\.+={1,2}|={1,2})\s*(?=\d+(?:[ ,.]\d+)*\b)', ' \u20b9 ', text_str).strip()
            blocks.append({
                "text": text_str,
                "confidence": round(float(confidence), 4),
                "bbox": norm_bbox,
            })
        except Exception as e:
            logger.warning(f"[OCR] Skipping malformed result item: {item!r} — {e}")
            continue
    logger.info(f"[OCR] Parsed {len(blocks)} text blocks.")
    return blocks


def _normalise_raw_ocr_result(raw_results: list) -> list:
    hindi_to_ascii = str.maketrans('०१२३४५६७८९', '0123456789')
    raw_payload = []
    for item in raw_results or []:
        try:
            if not item or len(item) < 3:
                continue
            bbox, text, confidence = item[0], item[1], item[2]
            text_str = str(text).translate(hindi_to_ascii)
            text_str = re.sub(r'(?:^|\s)(?:\.+={1,2}|={1,2})\s*(?=\d+(?:[ ,.]\d+)*\b)', ' \u20b9 ', text_str).strip()
            raw_payload.append({
                "bbox": [[round(float(pt[0]), 2), round(float(pt[1]), 2)] for pt in bbox],
                "text": text_str,
                "confidence": round(float(confidence), 4),
            })
        except Exception:
            continue
    return raw_payload


@app.post("/api/ocr/{image_id}")
async def run_ocr(image_id: int, user_id: str = Depends(get_current_user)):
    """Run OCR on a stored image and return structured results."""
    logger.info(f"[/api/ocr] Request: image_id={image_id}, user_id={user_id}")
    async with pool.acquire() as conn:
        record = await conn.fetchrow(
            "SELECT image_data, original_name FROM images WHERE id = $1 AND user_id = $2",
            image_id, user_id
        )
    if not record:
        raise HTTPException(status_code=404, detail="Image not found or unauthorized")

    data_uri: str = record['image_data']
    try:
        header, b64_content = data_uri.split(',', 1)
        image_bytes = base64.b64decode(b64_content)
        logger.info(f"[/api/ocr] Decoded {len(image_bytes)} bytes from DB for image {image_id}")
    except Exception as e:
        logger.error(f"[/api/ocr] Base64 decode failed: {e}")
        raise HTTPException(status_code=422, detail="Stored image data is malformed")

    loop = asyncio.get_event_loop()
    try:
        raw_results = await loop.run_in_executor(None, _run_ocr_sync, image_bytes)
    except Exception as e:
        logger.error(f"[/api/ocr] OCR failed for image {image_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"OCR error: {str(e)}")

    blocks = _parse_ocr_result(raw_results)
    avg_confidence = round(sum(b['confidence'] for b in blocks) / len(blocks), 4) if blocks else 0.0
    ocr_structure = parse_ocr_structure(blocks)
    logger.info(f"[/api/ocr] Complete: image_id={image_id}, blocks={len(blocks)}, avg_conf={avg_confidence}")
    return {
        "image_id": image_id,
        "filename": record['original_name'],
        "total_blocks": len(blocks),
        "avg_confidence": avg_confidence,
        "blocks": blocks,
        "full_text": ocr_structure.get("full_text", ""),
        "lines": ocr_structure.get("lines", []),
        "rows": ocr_structure.get("rows", []),
        "columns": ocr_structure.get("columns", []),
    }


@app.post("/api/pii/{image_id}")
async def run_pii_scan(image_id: int, user_id: str = Depends(get_current_user)):
    """
    Full DPDP PII scan pipeline:
      1. OCR the stored image
      2. Generate candidate entities from regex, validators, layout, and context
      3. Resolve final entities with AI semantic reasoning + confidence fusion
      4. Run compliance checks and AI audit reasoning
    """
    logger.info(f"[/api/pii] Request: image_id={image_id}, user_id={user_id}")

    # ── Step 1: Fetch image from DB ───────────────────────────────────────────
    async with pool.acquire() as conn:
        record = await conn.fetchrow(
            "SELECT image_data, original_name FROM images WHERE id = $1 AND user_id = $2",
            image_id, user_id
        )
    if not record:
        logger.warning(f"[/api/pii] Image {image_id} not found for user '{user_id}'")
        raise HTTPException(status_code=404, detail="Image not found or unauthorized")

    data_uri: str = record['image_data']
    try:
        header, b64_content = data_uri.split(',', 1)
        image_bytes = base64.b64decode(b64_content)
        logger.info(f"[/api/pii] Decoded {len(image_bytes)} bytes from DB")
    except Exception as e:
        logger.error(f"[/api/pii] Base64 decode failed: {e}")
        raise HTTPException(status_code=422, detail=f"Stored image data is malformed: {e}")

    # ── Step 2: OCR ───────────────────────────────────────────────────────────
    loop = asyncio.get_event_loop()
    try:
        raw_results = await loop.run_in_executor(None, _run_ocr_sync, image_bytes)
    except Exception as e:
        logger.error(f"[/api/pii] OCR failed for image {image_id}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"OCR engine error: {str(e)}")

    ocr_blocks = _parse_ocr_result(raw_results)
    avg_confidence = (
        round(sum(b['confidence'] for b in ocr_blocks) / len(ocr_blocks), 4)
        if ocr_blocks else 0.0
    )
    ocr_structure = parse_ocr_structure(ocr_blocks)
    full_text = ocr_structure.get("full_text", "")
    ocr_payload = {
        "total_blocks": len(ocr_blocks),
        "avg_confidence": avg_confidence,
        "blocks": ocr_blocks,
        "full_text": full_text,
        "lines": ocr_structure.get("lines", []),
        "rows": ocr_structure.get("rows", []),
        "columns": ocr_structure.get("columns", []),
    }
    logger.info(f"[/api/pii] OCR done: {len(ocr_blocks)} blocks, avg_conf={avg_confidence}")

    # ── Step 3: PII detection ─────────────────────────────────────────────────
    document_type = classify_document(ocr_blocks, full_text)
    mime_type = "image/jpeg"
    if header.startswith("data:") and ";" in header:
        mime_type = header[5:].split(";", 1)[0] or mime_type

    try:
        candidate_payload = await loop.run_in_executor(
            None,
            generate_entity_candidates,
            ocr_blocks,
            ocr_structure,
            document_type,
        )
        logger.info(
            "[/api/pii] Candidate generation done: %s candidates",
            len(candidate_payload.get("candidates", [])),
        )

        semantic_task = partial(
            analyze_entity_candidates,
            image_bytes=image_bytes,
            mime_type=mime_type,
            ocr=ocr_payload,
            candidate_payload=candidate_payload,
            document_type=document_type,
            metadata={
                "filename": record["original_name"],
                "image_id": image_id,
                "pipeline": "OCR -> Candidate Evidence -> AI Semantic Resolution -> Entity Resolver",
            },
        )
        semantic_resolution = await loop.run_in_executor(None, semantic_task)
        entities = await loop.run_in_executor(None, resolve_entities, candidate_payload, semantic_resolution)
        logger.info(
            "[/api/pii] Hybrid entity resolution done: semantic_status=%s final_entities=%s",
            semantic_resolution.get("status"),
            len(entities),
        )
    except Exception as e:
        logger.error(f"[/api/pii] Hybrid entity resolution failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"PII detection error: {str(e)}")

    # ── Step 4: DPDP Rules Engine evaluation ──────────────────────────────────
    try:
        dpdp_verdict = evaluate_dpdp_compliance(
            ocr_full_text=full_text,
            ocr_blocks=ocr_blocks,
            entities=entities,
            avg_ocr_confidence=avg_confidence,
        )
        # Build compliance dict from verdict
        compliance = {
            "total_entities": dpdp_verdict["total_entities"],
            "by_risk": dpdp_verdict["by_risk"],
        }
        logger.info(
            "[/api/pii] DPDP verdict=%s violations=%d severity=%s",
            dpdp_verdict["violations_found"],
            len(dpdp_verdict["violation_details"]),
            dpdp_verdict["overall_severity"],
        )
    except Exception as e:
        logger.error(f"[/api/pii] DPDP rules engine failed: {e}")
        dpdp_verdict = None
        compliance = {
            "total_entities": len(entities), "by_risk": {}
        }

    provider_diagnostics = get_provider_diagnostics()
    logger.info(
        "[/api/pii] AI provider=%s configured=%s model=%s",
        provider_diagnostics.get("provider"),
        provider_diagnostics.get("configured"),
        provider_diagnostics.get("model"),
    )

    # AI reasoning is intentionally separate from route/controller logic.
    try:
        ai_task = partial(
            analyze_dpdp_compliance,
            image_bytes=image_bytes,
            mime_type=mime_type,
            ocr=ocr_payload,
            entities=entities,
            compliance=compliance,
            document_type=document_type,
            candidate_payload=candidate_payload,
            semantic_resolution=semantic_resolution,
            metadata={
                "filename": record["original_name"],
                "image_id": image_id,
                "pipeline": "OCR -> Candidate Generation -> AI Entity Resolution -> Compliance -> Vision Audit Reasoning",
            },
        )
        ai_analysis = await loop.run_in_executor(None, ai_task)
        logger.info(
            f"[/api/pii] AI reasoning status={ai_analysis.get('status')}, "
            f"combined_score={ai_analysis.get('risk_score', {}).get('score')}"
        )
    except Exception as e:
        logger.error(f"[/api/pii] AI reasoning wrapper failed: {e}\n{traceback.format_exc()}")
        ai_analysis = {
            "enabled": False,
            "provider": provider_diagnostics.get("provider", "unknown"),
            "status": "fallback",
            "error": "AI reasoning failed unexpectedly.",
            "document_type": classify_document(ocr_blocks, full_text),
            "ai_summary": "Rule-based DPDP analysis completed; AI reasoning was unavailable.",
            "overall_risk": "Low",
            "screen_sensitivity": "Low",
            "purpose_limitation": {
                "assessment": "Unavailable.",
                "excessive_data_exposure": False,
            },
            "findings": [],
            "recommendations": [],
            "observations": [],
            "limitations": ["AI reasoning layer failed after rule-based analysis completed."],
            "risk_score": {
                "score": 0,
                "severity": "Low",
                "readiness": "Rule-Based Only",
                "base_rule_score": 0,
            },
        }

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM images WHERE id = $1 AND user_id = $2",
                image_id, user_id
            )
        logger.info(f"[/api/pii] Deleted transient image {image_id} after analysis")
    except Exception as e:
        logger.warning(f"[/api/pii] Could not delete transient image {image_id}: {e}")

    logger.info(
        f"[/api/pii] Complete: image_id={image_id}, "
        f"entities={len(entities)}"
    )
    return {
        "image_id": image_id,
        "filename": record['original_name'],
        "ocr": {
            "total_blocks": ocr_payload["total_blocks"],
            "avg_confidence": ocr_payload["avg_confidence"],
            "blocks": ocr_payload["blocks"],
            "full_text": ocr_payload["full_text"],
            "lines": ocr_payload["lines"],
            "rows": ocr_payload["rows"],
            "columns": ocr_payload["columns"],
        },
        "entities": entities,
        "compliance": compliance,
        "dpdp_verdict": dpdp_verdict,
        "candidate_entities": candidate_payload.get("candidates", []),
        "semantic_resolution": semantic_resolution,
        "ai_analysis": ai_analysis,
    }


@app.post("/api/ocr-debug")
async def ocr_debug(image: UploadFile = File(...), user_id: str = Depends(get_current_user)):
    """
    Debug endpoint: upload an image directly and return the full OCR/layout
    inspection payload, including visual overlay and mapping decisions.
    """
    logger.info(f"[/api/ocr-debug] file={image.filename}, content_type={image.content_type}")
    try:
        image_bytes = await image.read()
        logger.info(f"[/api/ocr-debug] Read {len(image_bytes)} bytes")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read uploaded file: {e}")

    loop = asyncio.get_event_loop()
    try:
        raw_results = await loop.run_in_executor(None, _run_ocr_sync, image_bytes)
    except Exception as e:
        logger.error(f"[/api/ocr-debug] OCR failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"OCR error: {str(e)}")

    blocks = _parse_ocr_result(raw_results)
    ocr_structure = parse_ocr_structure(blocks)
    full_text = ocr_structure.get("full_text", "")
    document_type = classify_document(blocks, full_text)
    candidate_payload = generate_entity_candidates(blocks, ocr_structure, document_type)
    semantic_resolution = {
        "status": "debug_deterministic_only",
        "entity_classifications": [],
        "screen_semantics": {},
        "limitations": ["OCR debug endpoint does not call AI semantic resolution."],
    }
    entities = resolve_entities(candidate_payload, semantic_resolution)
    layout_debug = candidate_payload.get("layout_debug") or build_layout_debug(blocks, ocr_structure, document_type)
    annotated_image = render_ocr_debug_overlay(
        image_bytes,
        blocks=blocks,
        structure=ocr_structure,
        entities=entities,
        layout_debug=layout_debug,
    )

    logger.info(
        "[/api/ocr-debug] structure blocks=%s rows=%s columns=%s labels=%s mappings=%s entities=%s",
        len(blocks),
        len(ocr_structure.get("rows", [])),
        len(ocr_structure.get("columns", [])),
        len(layout_debug.get("labels", [])),
        len(layout_debug.get("selected_mappings", [])),
        len(entities),
    )

    return {
        "filename": image.filename,
        "total_blocks": len(blocks),
        "document_type": document_type,
        "full_text": full_text,
        "raw_ocr_results": _normalise_raw_ocr_result(raw_results),
        "ocr": {
            "blocks": blocks,
            "structure_blocks": ocr_structure.get("blocks", []),
            "lines": ocr_structure.get("lines", []),
            "rows": ocr_structure.get("rows", []),
            "columns": ocr_structure.get("columns", []),
            "full_text": full_text,
        },
        "layout_debug": layout_debug,
        "candidate_entities": candidate_payload.get("candidates", []),
        "semantic_resolution": semantic_resolution,
        "entities": entities,
        "annotated_image": annotated_image,
    }


# ── /api/analyze-ai — Text-based AI reasoning endpoint ──────────────────

class AnalyzeAiRequest(BaseModel):
    """
    Standalone AI analysis request.
    Accepts the same OCR/entity/compliance payload that /api/pii already produces,
    so callers can either:
      (a) hit this endpoint directly with a stored scan result, or
      (b) let the /api/pii pipeline call run_text_analysis() internally.
    """
    document_type: str = "Unknown"
    ocr: dict = {}
    entities: list = []
    compliance: dict = {}
    metadata: dict = {}


@app.post("/api/analyze-ai", tags=["AI Reasoning"])
async def analyze_ai(
    request: AnalyzeAiRequest,
    user: dict = Depends(get_current_user),
):
    """
    Run text-based AI reasoning against an OCR/PII extraction payload.

    **Model**: Generic AI model (text-only, no vision).

    Accepts the structured output from /api/pii (or /api/ocr) and returns a
    DPDP compliance reasoning report with findings, risk score, and recommendations.

    Gracefully falls back to deterministic analysis if HF inference is unavailable.
    """
    loop = asyncio.get_event_loop()
    logger.info(
        "[/api/analyze-ai] user=%s doc_type=%s entities=%d model=%s",
        user.get("sub"), request.document_type, len(request.entities), HF_TEXT_MODEL,
    )
    try:
        ai_result = await loop.run_in_executor(
            None,
            lambda: run_text_analysis(
                document_type=request.document_type,
                ocr=request.ocr,
                entities=request.entities,
                compliance=request.compliance,
                metadata=request.metadata,
            ),
        )
    except Exception as exc:
        logger.error("[/api/analyze-ai] Unexpected error: %s", exc)
        raise HTTPException(status_code=500, detail=f"AI analysis error: {exc}")

    logger.info(
        "[/api/analyze-ai] Done: status=%s overall_risk=%s findings=%d",
        ai_result.get("status"),
        ai_result.get("overall_risk"),
        len(ai_result.get("findings", [])),
    )
    return ai_result


# ── ROPA Generation Endpoints ─────────────────────────────────────────────────

class RopaGenerateRequest(BaseModel):
    scan_results: list = []
    process_context: dict = {}

class RopaExportRequest(BaseModel):
    ropa_entries: list = []
    personal_data_inventory: dict = {}
    metadata: dict = {}


@app.post("/api/ropa/generate", tags=["ROPA"])
async def ropa_generate(
    request: RopaGenerateRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Generate a ROPA entry from DPDP scan results.
    Maps PII entities, violations, and AI analysis into the
    SIB Fiduciary ROPA template structure (31 columns).
    """
    logger.info(
        "[/api/ropa/generate] user=%s scans=%d",
        user_id, len(request.scan_results),
    )
    try:
        result = generate_ropa_entry(
            scan_results=request.scan_results,
            process_context=request.process_context,
            serial=1,
        )
        pdi = generate_personal_data_inventory(
            result.get("pii_inventory", {})
        )
        result["personal_data_inventory"] = pdi
        logger.info(
            "[/api/ropa/generate] Done: completion=%d%% warnings=%d",
            result["validation"]["completion_pct"],
            len(result["validation"]["warnings"]),
        )
        return result
    except Exception as e:
        logger.error("[/api/ropa/generate] Error: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"ROPA generation error: {e}")


@app.post("/api/ropa/export", tags=["ROPA"])
async def ropa_export(
    request: RopaExportRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Export populated ROPA as an Excel file (.xlsx).
    Uses the SIB template and injects field values.
    Returns raw bytes with proper Content-Disposition header.
    """
    from fastapi.responses import Response
    logger.info(
        "[/api/ropa/export] user=%s entries=%d",
        user_id, len(request.ropa_entries),
    )
    if not request.ropa_entries:
        raise HTTPException(status_code=400, detail="No ROPA entries to export.")

    try:
        buffer = export_ropa_xlsx(
            ropa_entries=request.ropa_entries,
            personal_data_inventory=request.personal_data_inventory,
            metadata=request.metadata,
        )
        xlsx_bytes = buffer.getvalue()
        filename = "SIB_DPDPA_Fiduciary_ROPA.xlsx"

        logger.info("[/api/ropa/export] Generated %s (%d bytes)", filename, len(xlsx_bytes))
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(xlsx_bytes)),
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )
    except FileNotFoundError as e:
        logger.error("[/api/ropa/export] Template not found: %s", e)
        raise HTTPException(status_code=500, detail=f"ROPA template file not found: {e}")
    except Exception as e:
        logger.error("[/api/ropa/export] Error: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"ROPA export error: {e}")

@app.post("/api/apk/upload")
async def upload_apk(apk: UploadFile = File(...), user=Depends(get_current_user)):
    path = f"/tmp/apk_{uuid.uuid4()}.apk"
    with open(path, "wb") as f:
        f.write(await apk.read())
    static_info = analyze_apk(path)              # instant, no emulator
    job = create_job(user_id=user, apk_path=path)
    update_job(job.job_id, static_info=static_info, status="ready")
    return {"job_id": job.job_id, "static_info": static_info}

@app.post("/api/apk/start/{job_id}")
async def start_apk_analysis(job_id: str, bg: BackgroundTasks, user=Depends(get_current_user)):
    job = get_job(job_id)
    if not job or job.user_id != user:
        raise HTTPException(404)
    update_job(job_id, status="running", progress=10)
    bg.add_task(_run_apk_job, job_id, user)
    return {"status": "started"}

@app.get("/api/apk/status/{job_id}")
async def apk_status(job_id: str, user=Depends(get_current_user)):
    job = get_job(job_id)
    if not job or job.user_id != user:
        raise HTTPException(404)
    return {
        "job_id": job.job_id, "status": job.status,
        "progress": job.progress, "message": job.message,
        "screenshot_count": len(job.screenshots),
        "image_ids": job.screenshots,
        "static_info": job.static_info, "error": job.error
    }

async def _run_apk_job(job_id: str, user_id: str):
    job = get_job(job_id)
    try:
        si = job.static_info
        update_job(job_id, status="navigating", progress=20, message="Launching app...")
        screenshots = await navigate_and_capture(
            job_id, job.apk_path, si["package_name"], si["main_activity"]
        )
        update_job(job_id, status="processing", progress=85, message="Saving screenshots...")
        image_ids = []
        for i, img_bytes in enumerate(screenshots):
            b64 = "data:image/png;base64," + base64.b64encode(img_bytes).decode()
            async with pool.acquire() as conn:
                img_id = await conn.fetchval(
                    "INSERT INTO images (user_id,original_name,filename,image_data) "
                    "VALUES ($1,$2,$3,$4) RETURNING id",
                    user_id, f"apk_screen_{i}.png", f"apk_screen_{i}.png", b64
                )
            image_ids.append(img_id)
        update_job(job_id, status="done", progress=100,
                   screenshots=image_ids, message=f"Captured {len(image_ids)} screens")
    except Exception as e:
        update_job(job_id, status="failed", error=str(e))
    finally:
        if os.path.exists(job.apk_path):
            os.remove(job.apk_path)


# ── Dev Baseline Endpoint ─────────────────────────────────────────────────────

class BaselineRequest(BaseModel):
    file_name: str
    payload: dict

@app.post("/api/dev/baseline", tags=["Developer"])
async def save_dev_baseline(
    request: BaselineRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Save a developer baseline snapshot for regression testing.
    Stores the full scan payload + corrections_expected list.
    """
    import json as _json
    if not request.file_name or not request.file_name.strip():
        raise HTTPException(status_code=400, detail="file_name is required.")

    logger.info(
        "[/api/dev/baseline] user=%s file_name=%s payload_keys=%s",
        user_id, request.file_name, list(request.payload.keys()),
    )
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT id FROM dev_baselines WHERE user_id = $1 AND file_name = $2",
            user_id, request.file_name.strip()
        )
        if existing:
            raise HTTPException(status_code=409, detail="A baseline with this name already exists. Please type a new name.")

        row = await conn.fetchrow(
            """
            INSERT INTO dev_baselines (user_id, file_name, payload)
            VALUES ($1, $2, $3::jsonb)
            RETURNING id, file_name, created_at
            """,
            user_id,
            request.file_name.strip(),
            _json.dumps(request.payload),
        )
    logger.info("[/api/dev/baseline] Saved baseline id=%s", row["id"])
    return {
        "id": row["id"],
        "file_name": row["file_name"],
        "created_at": row["created_at"].isoformat(),
    }


@app.get("/api/dev/baseline", tags=["Developer"])
async def list_dev_baselines(user_id: str = Depends(get_current_user)):
    """
    Return every baseline file belonging to the authenticated user,
    ordered newest-first.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, file_name, created_at FROM dev_baselines "
            "WHERE user_id = $1 ORDER BY created_at DESC",
            user_id,
        )
    logger.info("[GET /api/dev/baseline] user=%s count=%d", user_id, len(rows))
    return [
        {
            "id": r["id"],
            "file_name": r["file_name"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]



@app.get("/api/dev/baseline/{baseline_id}", tags=["Developer"])
async def get_dev_baseline(
    baseline_id: int,
    user_id: str = Depends(get_current_user),
):
    """
    Return a single baseline with its full JSONB payload.
    Used by the frontend for client-side correction comparison.
    """
    import json as _json
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, user_id, file_name, created_at, payload "
            "FROM dev_baselines WHERE id = $1",
            baseline_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Baseline not found.")
    if row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorised to view this baseline.")
    logger.info("[GET /api/dev/baseline/%s] user=%s", baseline_id, user_id)
    return {
        "id": row["id"],
        "file_name": row["file_name"],
        "created_at": row["created_at"].isoformat(),
        "payload": _json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"],
    }


@app.delete("/api/dev/baseline/{baseline_id}", tags=["Developer"])
async def delete_dev_baseline(
    baseline_id: int,
    user_id: str = Depends(get_current_user),
):
    """
    Permanently delete a baseline file.
    Returns 404 if the ID does not exist, 403 if the row belongs to
    another user.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, user_id FROM dev_baselines WHERE id = $1",
            baseline_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Baseline not found.")
        if row["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorised to delete this baseline.")
        await conn.execute("DELETE FROM dev_baselines WHERE id = $1", baseline_id)
    logger.info("[DELETE /api/dev/baseline/%s] deleted by user=%s", baseline_id, user_id)
    return {"message": "Baseline deleted.", "id": baseline_id}
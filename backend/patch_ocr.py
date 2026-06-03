import re

with open('main.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_func = """def _run_ocr_sync(image_bytes: bytes) -> list:
    \"\"\"
    Run EasyOCR synchronously in a thread pool.
    EasyOCR returns: [ [bbox, text, confidence], ... ]
    where bbox = [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
    \"\"\"
    logger.info(f"[OCR] Starting OCR on image ({len(image_bytes)} bytes)")
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
        logger.error(f"[OCR] Exception in _run_ocr_sync: {e}\\n{traceback.format_exc()}")
        raise"""

new_func = """def _run_ocr_sync(image_bytes: bytes) -> list:
    \"\"\"
    Run EasyOCR synchronously in a thread pool.
    EasyOCR returns: [ [bbox, text, confidence], ... ]
    where bbox = [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
    \"\"\"
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
            logger.error(f"[OCR] Exception in _run_ocr_sync: {e}\\n{traceback.format_exc()}")
            raise"""

# Handle crlf vs lf
old_func = old_func.replace('\r\n', '\n')
new_func = new_func.replace('\r\n', '\n')

# Convert code to LF for safe matching
code_lf = code.replace('\r\n', '\n')

if old_func in code_lf:
    code_lf = code_lf.replace(old_func, new_func)
    
    # Write back keeping original line endings if possible, or just write LF (Python handles it)
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(code_lf)
    print("Patched successfully")
else:
    print("Could not find old_func in main.py")

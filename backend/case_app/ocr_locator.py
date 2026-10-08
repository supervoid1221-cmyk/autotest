import csv
import difflib
import io
import os
import shutil
import subprocess
import tempfile


class OCRLocatorError(RuntimeError):
    pass


def _normalized(value):
    return "".join(str(value or "").lower().split())


def _ocr_lines(image_content):
    command = os.getenv("APP_OCR_TESSERACT_CMD", "tesseract")
    executable = shutil.which(command)
    if not executable:
        raise OCRLocatorError("未安装 Tesseract OCR，请先安装并配置 APP_OCR_TESSERACT_CMD。")
    requested_languages = [item.strip() for item in os.getenv("APP_OCR_LANGUAGES", "chi_sim+eng").split("+") if item.strip()]
    language_result = subprocess.run(
        [executable, "--list-langs"], capture_output=True, text=True, timeout=5, check=False,
    )
    installed_languages = {
        line.strip() for line in language_result.stdout.splitlines()
        if line.strip() and not line.lower().startswith("list of available")
    }
    selected_languages = [item for item in requested_languages if item in installed_languages]
    path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as image:
            image.write(image_content)
            path = image.name
        arguments = [executable, path, "stdout"]
        if selected_languages:
            arguments.extend(["-l", "+".join(selected_languages)])
        arguments.append("tsv")
        process = subprocess.run(
            arguments,
            capture_output=True, text=True, timeout=25, check=False,
        )
        if process.returncode:
            message = (process.stderr or process.stdout or "OCR 执行失败").strip()
            raise OCRLocatorError(message[:500])
        groups = {}
        for row in csv.DictReader(io.StringIO(process.stdout), delimiter="\t"):
            text = str(row.get("text") or "").strip()
            if not text:
                continue
            try:
                confidence = float(row.get("conf") or -1)
                left, top = int(row["left"]), int(row["top"])
                width, height = int(row["width"]), int(row["height"])
            except (TypeError, ValueError, KeyError):
                continue
            if confidence < 0 or width <= 0 or height <= 0:
                continue
            key = tuple(row.get(field) for field in ("page_num", "block_num", "par_num", "line_num"))
            groups.setdefault(key, []).append({
                "text": text, "left": left, "top": top, "right": left + width,
                "bottom": top + height, "confidence": confidence,
            })
        return list(groups.values())
    except subprocess.TimeoutExpired as exc:
        raise OCRLocatorError("OCR 识别超时，请检查截图大小或 OCR 服务。") from exc
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


def locate_text(image_content, target, fuzzy=False):
    expected = _normalized(target)
    if not expected:
        raise OCRLocatorError("请输入需要识别的文字。")
    best = None
    for words in _ocr_lines(image_content):
        for start in range(len(words)):
            combined = ""
            for end in range(start, len(words)):
                combined += _normalized(words[end]["text"])
                if not combined:
                    continue
                if fuzzy:
                    score = difflib.SequenceMatcher(None, expected, combined).ratio()
                    matched = expected in combined or combined in expected or score >= 0.72
                else:
                    score = 1.0 if combined == expected else 0.95 if expected in combined else 0
                    matched = score > 0
                if matched:
                    selected = words[start:end + 1]
                    confidence = sum(item["confidence"] for item in selected) / len(selected)
                    candidate = {
                        "text": " ".join(item["text"] for item in selected),
                        "left": min(item["left"] for item in selected),
                        "top": min(item["top"] for item in selected),
                        "right": max(item["right"] for item in selected),
                        "bottom": max(item["bottom"] for item in selected),
                        "confidence": round(confidence, 2), "score": score,
                    }
                    if best is None or (candidate["score"], candidate["confidence"]) > (best["score"], best["confidence"]):
                        best = candidate
                if len(combined) > max(len(expected) * 2, len(expected) + 12):
                    break
    if not best:
        raise OCRLocatorError(f"未在当前画面识别到文字「{target}」。")
    best["x"] = round((best["left"] + best["right"]) / 2)
    best["y"] = round((best["top"] + best["bottom"]) / 2)
    return best

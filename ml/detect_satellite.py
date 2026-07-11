"""YOLOv8 vehicle detection on static aerial parking-lot images -> JSON + overlays.

Dominic's satellite pipeline. For each store it runs detection on the
before/after images in ml/sample_images/, then:

  1. writes annotated overlay images to frontend/public/samples/ — the exact
     paths the seed rows in backend/database.py serve as image_url, so the
     ImageCompare panel shows real boxes with zero backend changes
  2. writes ml/detections.json — per-snapshot vehicle counts and pixel boxes,
     for Nelson's fusion (Trends interest vs. satellite ground-truth) and for
     the Gemini narrative payload
  3. with --ingest, upserts the snapshot rows into perigee.db via
     backend/ingest.replace_satellite so captured_at/image_url stay in sync

The snapshot fields (captured_at, image_url) match backend/schemas.py
SatelliteSnapshot; counts/boxes ride alongside in the JSON for the signals
layer, which reads files, not the API.

Usage:
    python ml/detect_satellite.py            # detect + overlays + JSON
    python ml/detect_satellite.py --ingest   # also write rows into perigee.db

Deps: pip install ultralytics opencv-python-headless (plus pydantic for --ingest).
"""

import argparse
import json
import sys
from pathlib import Path

import cv2
from ultralytics import YOLO

ML_DIR = Path(__file__).parent
REPO = ML_DIR.parent
MODEL_PATH = ML_DIR / "models" / "yolov8n.pt"
IMAGES_DIR = ML_DIR / "sample_images"
OVERLAY_DIR = REPO / "frontend" / "public" / "samples"
OUTPUT_JSON = ML_DIR / "detections.json"

# Detection contract per fileSchema.md: conf=0.25, class=car -> count + boxes.
CONF = 0.25
IMGSZ = 1280  # native width of the aerial captures; 640 misses the small cars
CAR_CLASSES = {2: "car"}  # COCO id 2

BOX_COLOR = (80, 220, 80)  # BGR
BADGE_BG = (30, 30, 30)

# captured_at dates mirror the seed rows in backend/database.py so the
# EDGAR/Trends timeline story lines up across panels.
SNAPSHOTS = [
    {"store_id": 1, "kind": "before", "captured_at": "2026-05-14"},
    {"store_id": 1, "kind": "after", "captured_at": "2026-06-29"},
    {"store_id": 2, "kind": "before", "captured_at": "2026-05-20"},
    {"store_id": 2, "kind": "after", "captured_at": "2026-06-28"},
    {"store_id": 3, "kind": "before", "captured_at": "2026-05-11"},
    {"store_id": 3, "kind": "after", "captured_at": "2026-06-30"},
]


def detect_vehicles(model, image_path):
    """Run YOLOv8 on one image; return (boxes, annotated image).

    boxes: list of {x1, y1, x2, y2, confidence, label} in pixel coords,
    vehicle classes only.
    """
    result = model.predict(str(image_path), conf=CONF, imgsz=IMGSZ, verbose=False)[0]
    img = cv2.imread(str(image_path))
    boxes = []
    for box in result.boxes:
        cls = int(box.cls)
        if cls not in CAR_CLASSES:
            continue
        x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
        boxes.append({
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "confidence": round(float(box.conf), 3),
            "label": CAR_CLASSES[cls],
        })
        cv2.rectangle(img, (x1, y1), (x2, y2), BOX_COLOR, 2)
    return boxes, img


def draw_count_badge(img, count):
    """Stamp a 'N cars' badge in the top-left corner of the overlay."""
    text = f"{count} cars"
    font, scale, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thick)
    pad = 10
    cv2.rectangle(img, (0, 0), (tw + 2 * pad, th + baseline + 2 * pad), BADGE_BG, -1)
    cv2.putText(img, text, (pad, pad + th), font, scale, BOX_COLOR, thick, cv2.LINE_AA)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ingest", action="store_true",
                        help="also write snapshot rows into perigee.db")
    args = parser.parse_args()

    model = YOLO(str(MODEL_PATH))
    OVERLAY_DIR.mkdir(parents=True, exist_ok=True)

    detections = []
    for snap in SNAPSHOTS:
        name = f"store{snap['store_id']}_{snap['kind']}.jpg"
        src = IMAGES_DIR / name
        if not src.exists():
            print(f"skip {name}: source image missing", file=sys.stderr)
            continue

        boxes, overlay = detect_vehicles(model, src)
        draw_count_badge(overlay, len(boxes))
        cv2.imwrite(str(OVERLAY_DIR / name), overlay)

        detections.append({
            "store_id": snap["store_id"],
            "kind": snap["kind"],
            "captured_at": snap["captured_at"],
            "image_url": f"/samples/{name}",
            "car_count": len(boxes),
            "boxes": boxes,
        })
        print(f"store {snap['store_id']} {snap['kind']:6s}: "
              f"{len(boxes):3d} cars -> {OVERLAY_DIR / name}")

    OUTPUT_JSON.write_text(json.dumps({
        "model": MODEL_PATH.name,
        "confidence_threshold": CONF,
        "classes": sorted(CAR_CLASSES.values()),
        "detections": detections,
    }, indent=2) + "\n")
    print(f"wrote {OUTPUT_JSON}")

    if args.ingest:
        sys.path.insert(0, str(REPO / "backend"))
        import ingest

        for d in detections:
            ingest.replace_satellite(
                store_id=d["store_id"], kind=d["kind"],
                captured_at=d["captured_at"], image_url=d["image_url"],
                car_count=d["car_count"],
            )
        print("ingested snapshot rows into perigee.db")


if __name__ == "__main__":
    main()

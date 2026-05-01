"""
train_lens_segmentation.py
==========================
Fine-tunes YOLOv8n-seg on optical lens / eyewear images to produce
backend/models/lens_seg.pt — the lens segmentation model used at runtime.

Run this in Google Colab (free T4 GPU) or locally:
  python scripts/train_lens_segmentation.py

You need a Roboflow account (free) to download the datasets.
Set your API key as an environment variable:
  export ROBOFLOW_API_KEY="your_key_here"
Or pass it as an argument: --api-key your_key_here

Datasets used (all public/free on Roboflow Universe):
  1. lens-segmentation (primary — single-class 'lens' with polygon masks)
  2. glasses-segmentation (eyewear on faces — supplements lens on spectacles/goggles)
  3. Synthetic augmentation (generated here — solid ellipses to prevent overfitting)

Output:
  runs/lens_seg/weights/best.pt  → copied to  backend/models/lens_seg.pt
"""

import argparse
import os
import shutil
import sys
import yaml
import json
from pathlib import Path
from collections import defaultdict

# ── CLI args ──────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Train YOLOv8n-seg for lens segmentation")
parser.add_argument("--api-key",   default=os.getenv("ROBOFLOW_API_KEY", ""),
                    help="Roboflow API key (or set ROBOFLOW_API_KEY env var)")
parser.add_argument("--epochs",    type=int, default=60,
                    help="Training epochs (default 60; use 30 for quick test)")
parser.add_argument("--imgsz",     type=int, default=640)
parser.add_argument("--batch",     type=int, default=16)
parser.add_argument("--device",    default="cpu",
                    help="CUDA device index, or 'cpu'")
parser.add_argument("--output",    default="backend/models/lens_seg.pt",
                    help="Where to copy the final best.pt")
parser.add_argument("--skip-download", action="store_true",
                    help="Skip Roboflow download (use existing data/ folder)")
args = parser.parse_args()

# ── Imports (require ultralytics + roboflow) ──────────────────────────────────
try:
    from ultralytics import YOLO
except ImportError:
    print("ERROR: ultralytics not installed. Run:  pip install ultralytics")
    sys.exit(1)

try:
    from roboflow import Roboflow
    RF_AVAILABLE = True
except ImportError:
    RF_AVAILABLE = False
    print("WARNING: roboflow package not installed. Install with: pip install roboflow")
    print("         Continuing with synthetic data only (reduced accuracy).")

import cv2
import numpy as np
import random

# ── Root paths ──────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "lens_combined"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ROBOFLOW_DATASETS = [
    # (workspace, project, version)
    # Primary lens segmentation dataset (optical lenses, goggles, spectacles)
    ("lens-defect-detection-kgbfr", "lens-segmentation-v2",      2),
    # Glasses on faces — teaches the model glasses/goggles context
    ("computer-vision-projects-vr0y", "glasses-segmentation-2",  2),
    # Camera lens segmentation (circular optical element from camera equipment)
    ("lens-project",                 "camera-lens-segmentation",  1),
]


def find_local_dataset():
    local_data_root = ROOT_DIR / "data"
    train_json = local_data_root / "train" / "_annotations.coco.json"
    valid_json = local_data_root / "valid" / "_annotations.coco.json"
    print(f"DEBUG find_local_dataset: ROOT_DIR={ROOT_DIR}")
    print(f"DEBUG find_local_dataset: train_json={train_json}, exists={train_json.exists()}")
    print(f"DEBUG find_local_dataset: valid_json={valid_json}, exists={valid_json.exists()}")
    if train_json.exists() or valid_json.exists():
        return local_data_root, DATA_DIR / "local"
    return None, None


def download_datasets():
    if not RF_AVAILABLE:
        print("Skipping Roboflow download (package not installed).")
        return []
    local_data_root, local_dataset = find_local_dataset()
    if local_dataset is not None:
        print("No Roboflow download required; local COCO dataset found.")
        convert_coco_to_yolo(local_data_root, local_dataset)
        return [local_dataset]

    if not args.api_key:
        print(
            "\nNo Roboflow API key provided.\n"
            "Get a free key at https://roboflow.com and set it with:\n"
            "  export ROBOFLOW_API_KEY='your_key'\n"
            "Continuing with synthetic data only.\n"
        )
        return []

    rf      = Roboflow(api_key=args.api_key)
    paths   = []

    for workspace, project, version in ROBOFLOW_DATASETS:
        dest = DATA_DIR / project
        if dest.exists():
            print(f"  Already downloaded: {project}")
            paths.append(dest)
            continue
        try:
            print(f"  Downloading {workspace}/{project} v{version}...")
            proj    = rf.workspace(workspace).project(project)
            dataset = proj.version(version).download(
                "yolov8",
                location=str(dest),
                overwrite=False
            )
            paths.append(dest)
            print(f"  ✓ {project}")
        except Exception as e:
            print(f"  ✗ {project}: {e} (skipping)")

    return paths


# ── Synthetic data generation ─────────────────────────────────────────────────
def generate_synthetic(n_images=400, dest=DATA_DIR / "synthetic"):
    """
    Generates synthetic lens images:
      - Solid-colour ellipses on varied backgrounds
      - Multiple sizes and aspect ratios (round lenses, oval lenses, goggles)
      - Graduated glass-like gradients to simulate specular reflections

    Each image gets a corresponding YOLO-seg .txt label (class 0, polygon).
    """
    print(f"\nGenerating {n_images} synthetic lens images...")

    for split in ["train", "valid"]:
        (dest / split / "images").mkdir(parents=True, exist_ok=True)
        (dest / split / "labels").mkdir(parents=True, exist_ok=True)

    n_train = int(n_images * 0.85)
    n_valid = n_images - n_train

    def _make_bg(w, h):
        bg_type = random.choice(["solid", "gradient", "noise", "checkerboard"])
        if bg_type == "solid":
            c = [random.randint(20, 230)] * 3
            return np.full((h, w, 3), c, np.uint8)
        elif bg_type == "gradient":
            bg = np.zeros((h, w, 3), np.uint8)
            for ch in range(3):
                val = np.linspace(random.randint(10, 100), random.randint(100, 245), w)
                bg[:, :, ch] = np.tile(val, (h, 1)).astype(np.uint8)
            return bg
        elif bg_type == "noise":
            return np.random.randint(30, 200, (h, w, 3), np.uint8)
        else:
            bg = np.zeros((h, w, 3), np.uint8)
            cs = random.randint(20, 60)
            for yi in range(0, h, cs):
                for xi in range(0, w, cs):
                    c = random.randint(40, 200)
                    bg[yi:yi+cs, xi:xi+cs] = [c, c, c]
            return bg

    def _make_lens(w, h):
        img = _make_bg(w, h)

        # Lens ellipse parameters
        cx = random.randint(int(w * 0.2), int(w * 0.8))
        cy = random.randint(int(h * 0.2), int(h * 0.8))
        rx = random.randint(int(min(w, h) * 0.15), int(min(w, h) * 0.42))
        ry = int(rx * random.uniform(0.55, 1.0))   # slightly oval to perfectly round
        angle = random.randint(0, 179)

        # Draw lens as semi-transparent tinted ellipse (glass-like)
        overlay = img.copy()
        lens_color = [random.randint(80, 220) for _ in range(3)]
        cv2.ellipse(overlay, (cx, cy), (rx, ry), angle, 0, 360, lens_color, -1)

        # Glass-like gradient inside ellipse
        mask_e = np.zeros((h, w), np.uint8)
        cv2.ellipse(mask_e, (cx, cy), (rx, ry), angle, 0, 360, 255, -1)
        ys, xs = np.where(mask_e > 0)
        if len(xs) > 0:
            # Specular highlight: top-left bright spot
            for px, py in zip(xs[::4], ys[::4]):
                dist = np.sqrt((px - (cx - rx * 0.3)) ** 2 + (py - (cy - ry * 0.3)) ** 2)
                highlight = max(0, 1 - dist / (rx * 0.5))
                overlay[py, px] = np.clip(
                    np.array(overlay[py, px], float) + highlight * 80, 0, 255
                ).astype(np.uint8)

        # Lens rim
        cv2.ellipse(overlay, (cx, cy), (rx, ry), angle, 0, 360,
                    [max(0, c - 60) for c in lens_color], random.randint(2, 6))

        alpha = random.uniform(0.55, 0.85)
        img = cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)

        # YOLO-seg label: polygon of the ellipse
        n_pts   = 24
        angles  = np.linspace(0, 2 * np.pi, n_pts, endpoint=False)
        rad     = np.deg2rad(angle)
        pts_x   = cx + rx * np.cos(angles) * np.cos(rad) - ry * np.sin(angles) * np.sin(rad)
        pts_y   = cy + rx * np.cos(angles) * np.sin(rad) + ry * np.sin(angles) * np.cos(rad)
        pts_x   = np.clip(pts_x / w, 0, 1)
        pts_y   = np.clip(pts_y / h, 0, 1)
        label_pts = " ".join(f"{x:.6f} {y:.6f}" for x, y in zip(pts_x, pts_y))
        label   = f"0 {label_pts}"

        return img, label

    W, H = 640, 640
    for i in range(n_train + n_valid):
        split  = "train" if i < n_train else "valid"
        img, lbl = _make_lens(W, H)
        name   = f"synth_{i:05d}"
        cv2.imwrite(str(dest / split / "images" / f"{name}.jpg"), img)
        (dest / split / "labels" / f"{name}.txt").write_text(lbl)

    # data.yaml
    (dest / "data.yaml").write_text(yaml.dump({
        "path":  str(dest.resolve()),
        "train": "train/images",
        "val":   "valid/images",
        "names": {0: "lens"},
        "nc":    1,
    }))

    print(f"  ✓ Synthetic data saved to {dest}")
    return dest


# ── Merge datasets into one data.yaml ────────────────────────────────────────
def build_combined_yaml(rf_paths, synth_path):
    """
    Creates a combined data.yaml that points to all downloaded + synthetic data.
    YOLO supports multiple image/label directories via list syntax.
    """
    all_train_imgs = []
    all_val_imgs   = []

    for p in rf_paths:
        p = Path(p)
        # Roboflow exports: train/images, valid/images
        for d in [p / "train" / "images", p / "images" / "train"]:
            if d.exists():
                all_train_imgs.append(str(d.resolve()))
        for d in [p / "valid" / "images", p / "images" / "val"]:
            if d.exists():
                all_val_imgs.append(str(d.resolve()))

    for split, lst in [("train", all_train_imgs), ("valid", all_val_imgs)]:
        d = synth_path / split / "images"
        if d.exists():
            lst.append(str(d.resolve()))

    combined = {
        "path":  str(DATA_DIR.resolve()),
        "train": all_train_imgs  if all_train_imgs  else str((synth_path / "train" / "images").resolve()),
        "val":   all_val_imgs    if all_val_imgs    else str((synth_path / "valid" / "images").resolve()),
        "nc":    1,
        "names": {0: "lens"},
    }

    yaml_path = DATA_DIR / "combined.yaml"
    yaml_path.write_text(yaml.dump(combined, default_flow_style=False))
    print(f"\nCombined dataset config: {yaml_path}")

    total_train = sum(len(list(Path(d).glob("*.jpg")) + list(Path(d).glob("*.png")))
                      for d in (all_train_imgs if isinstance(all_train_imgs, list) else [all_train_imgs]))
    print(f"Training images (approx): {total_train}")

    return yaml_path


def convert_coco_to_yolo(src_root, dest_root):
    src_root = Path(src_root)
    dest_root = Path(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)

    for split in ["train", "valid"]:
        src_split = src_root / split
        json_path = src_split / "_annotations.coco.json"
        if not json_path.exists():
            continue

        with json_path.open("r", encoding="utf-8") as f:
            coco = json.load(f)

        images = {img["id"]: img for img in coco.get("images", [])}
        categories = {cat["id"]: cat for cat in coco.get("categories", [])}
        ann_by_image = defaultdict(list)

        for ann in coco.get("annotations", []):
            ann_by_image[ann["image_id"]].append(ann)

        out_img_dir = dest_root / split / "images"
        out_lbl_dir = dest_root / split / "labels"
        out_img_dir.mkdir(parents=True, exist_ok=True)
        out_lbl_dir.mkdir(parents=True, exist_ok=True)

        for image_id, image_info in images.items():
            src_img = src_split / image_info["file_name"]
            if not src_img.exists():
                print(f"WARNING: missing image {src_img}")
                continue
            shutil.copy2(src_img, out_img_dir / image_info["file_name"])

            label_lines = []
            for ann in ann_by_image.get(image_id, []):
                segmentation = ann.get("segmentation", [])
                if not segmentation:
                    continue

                # Roboflow COCO sometimes stores a list of polygon lists.
                polys = []
                if isinstance(segmentation, list) and segmentation and isinstance(segmentation[0], list):
                    polys = segmentation
                else:
                    polys = [segmentation]

                for poly in polys:
                    if not poly or len(poly) < 6:
                        continue

                    width = image_info["width"]
                    height = image_info["height"]
                    normalized = []
                    for x, y in zip(poly[0::2], poly[1::2]):
                        normalized.append(x / width)
                        normalized.append(y / height)

                    if any(p < 0 or p > 1 for p in normalized):
                        normalized = [max(0.0, min(1.0, p)) for p in normalized]

                    label_lines.append("0 " + " ".join(f"{v:.6f}" for v in normalized))

            if label_lines:
                label_path = out_lbl_dir / f"{Path(image_info['file_name']).stem}.txt"
                label_path.write_text("\n".join(label_lines))

        print(f"Converted COCO -> YOLOv8 seg for {split}: {len(images)} images")

    data_yaml = dest_root / "data.yaml"
    data_yaml.write_text(yaml.dump({
        "path":  str(dest_root.resolve()),
        "train": "train/images",
        "val":   "valid/images",
        "names": {0: "lens"},
        "nc":    1,
    }, default_flow_style=False))
    print(f"Converted dataset YAML: {data_yaml}")
    return dest_root


# ── Training ──────────────────────────────────────────────────────────────────
def train(yaml_path):
    print(f"\nStarting training — epochs={args.epochs}, imgsz={args.imgsz}, batch={args.batch}")
    model = YOLO("yolov8n-seg.pt")   # start from COCO pretrained nano-seg

    results = model.train(
        data       = str(yaml_path),
        epochs     = args.epochs,
        imgsz      = args.imgsz,
        batch      = args.batch,
        device     = args.device,
        project    = "runs",
        name       = "lens_seg",
        # Augmentation settings tuned for lens images
        hsv_h      = 0.02,    # minimal hue shift (glass colour is irrelevant)
        hsv_s      = 0.5,
        hsv_v      = 0.4,
        degrees    = 45,      # lenses can be at any angle
        translate  = 0.15,
        scale      = 0.5,
        flipud     = 0.3,
        fliplr     = 0.5,
        mosaic     = 0.8,
        copy_paste = 0.3,     # copy-paste augmentation helps with segmentation
        # Patience for early stopping
        patience   = 20,
        save_period= 10,
        # Segment head settings
        overlap_mask = True,
        mask_ratio   = 4,
    )

    best_pt = Path("runs/lens_seg/weights/best.pt")
    if best_pt.exists():
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(best_pt, out)
        print(f"\n✅  Model saved to: {out}")
        print(    "    Set env var:  LENS_SEG_MODEL_PATH=models/lens_seg.pt")
    else:
        print("WARNING: best.pt not found. Check runs/lens_seg/weights/")

    return results


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Lens Segmentation — YOLOv8n-seg Fine-Tuning")
    print("=" * 60)

    local_data_root, local_dataset = find_local_dataset()
    if local_dataset is not None:
        print("Found local COCO dataset export; converting to YOLOv8 segmentation format...")
        convert_coco_to_yolo(local_data_root, local_dataset)
        rf_paths = [local_dataset]
    else:
        if args.skip_download:
            rf_paths = [p for p in DATA_DIR.iterdir() if p.is_dir() and p.name != "synthetic"]
            print(f"Skipping download, using {len(rf_paths)} existing dataset(s)")
        else:
            rf_paths = download_datasets()

    synth = generate_synthetic(n_images=600)
    yaml  = build_combined_yaml(rf_paths, synth)
    train(yaml)

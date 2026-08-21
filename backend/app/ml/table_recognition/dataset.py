"""
Unified Dataset Loader for Table Recognition

Combines TabRecSet (CurveTabSet) and Tencent OCR datasets for multi-task training.

TabRecSet provides:
├── Table Detection (TD) → Table bounding boxes
├── Structure Recognition (TSR) → Rows, columns, cells
└── Content Recognition (TCR) → Cell text

Tencent OCR provides:
└── Text Recognition → Character-level text annotations
"""

import os
import json
import cv2
import torch
import numpy as np
from torch.utils.data import Dataset
from PIL import Image
from typing import Dict, List, Tuple, Optional, Any
import logging

logger = logging.getLogger(__name__)


class TableRecognitionDataset(Dataset):
    """
    Unified dataset for table recognition training.
    
    Combines TabRecSet (table detection + structure) and Tencent OCR (text).
    
    Args:
        data_dir: Base directory containing 'tabrecset' and 'tencent_ocr' folders
        split: 'train', 'val', or 'test'
        transform: Image transforms (resize, normalize, augmentation)
        target_size: (height, width) for image resizing
        use_all_styles: Use all three TabRecSet image styles
    """
    
    def __init__(
        self,
        data_dir: str = "/app/data",
        split: str = "train",
        transform: Optional[Any] = None,
        target_size: Tuple[int, int] = (512, 512),
        use_all_styles: bool = True,
    ):
        super().__init__()
        
        self.data_dir = data_dir
        self.split = split
        self.transform = transform
        self.target_size = target_size
        self.use_all_styles = use_all_styles
        
        # Paths
        self.tabrecset_dir = os.path.join(data_dir, "tabrecset")
        self.tencent_dir = os.path.join(data_dir, "tencent_ocr")
        
        # TabRecSet paths
        self.image_dirs = {
            "all_line": os.path.join(self.tabrecset_dir, "image", "english_all-line"),
            "no_line": os.path.join(self.tabrecset_dir, "image", "english_no-line"),
            "three_line": os.path.join(self.tabrecset_dir, "image", "english_three-line"),
        }
        self.td_annotations_dir = os.path.join(self.tabrecset_dir, "TD annotation", "english")
        self.tsr_tcr_annotations_dir = os.path.join(self.tabrecset_dir, "TSR_TCR_annotation", "english")
        
        # Tencent OCR path
        self.tencent_ocr_dir = os.path.join(self.tencent_dir, "english")
        
        # Load file IDs
        self.file_ids = self._load_file_ids()
        
        # Split into train/val/test
        self.file_ids = self._split_data(self.file_ids)
        
        logger.info(f"Loaded dataset: {len(self.file_ids)} samples for {split} split")
        logger.info(f"  TabRecSet styles: {list(self.image_dirs.keys())}")
        
    def _load_file_ids(self) -> List[str]:
        """
        Load all unique file IDs from the dataset.
        
        Returns:
            List of file IDs (e.g., ["00ud6wgg", "06g64oay", ...])
        """
        # Get IDs from TD annotations (all datasets share the same IDs)
        td_files = [f for f in os.listdir(self.td_annotations_dir) if f.endswith('.json')]
        file_ids = [f.replace('.json', '') for f in td_files]
        
        # Verify consistency with TSR_TCR and Tencent OCR
        tsr_tcr_files = [f for f in os.listdir(self.tsr_tcr_annotations_dir) if f.endswith('.json')]
        tsr_tcr_ids = [f.replace('.json', '') for f in tsr_tcr_files]
        
        # Verify with Tencent OCR
        tencent_files = [f for f in os.listdir(self.tencent_ocr_dir) if f.endswith('.json')]
        tencent_ids = [f.replace('.json', '') for f in tencent_files]
        
        # Intersect all IDs to ensure consistency
        common_ids = set(file_ids) & set(tsr_tcr_ids) & set(tencent_ids)
        
        if len(common_ids) < len(file_ids):
            logger.warning(f"Found {len(common_ids)} common IDs out of {len(file_ids)}")
        
        return sorted(list(common_ids))
    
    def _split_data(self, file_ids: List[str]) -> List[str]:
        """
        Split data into train/val/test based on existing split files or random split.
        
        Returns:
            List of file IDs for this split
        """
        # Try to load split files if they exist
        split_file = os.path.join(self.data_dir, f"{self.split}_files.txt")
        
        if os.path.exists(split_file):
            with open(split_file, 'r') as f:
                split_ids = [line.strip() for line in f.readlines()]
            return split_ids
        
        # If no split files, do a random split (80/10/10)
        np.random.seed(42)
        indices = np.random.permutation(len(file_ids))
        
        train_end = int(0.8 * len(file_ids))
        val_end = int(0.9 * len(file_ids))
        
        if self.split == 'train':
            return [file_ids[i] for i in indices[:train_end]]
        elif self.split == 'val':
            return [file_ids[i] for i in indices[train_end:val_end]]
        elif self.split == 'test':
            return [file_ids[i] for i in indices[val_end:]]
        
        return file_ids
    
    def __len__(self) -> int:
        return len(self.file_ids)
    
    def __getitem__(self, idx: int) -> Dict[str, Any]:
        """
        Get a single training sample.
        
        Returns:
            Dictionary containing:
            ├── image: (C, H, W) tensor
            ├── table_bbox: (4,) tensor [x1, y1, x2, y2]
            ├── cells: List of cell annotations
            ├── structure: {'rows': int, 'cols': int}
            └── text: List of text strings
        """
        file_id = self.file_ids[idx]
        
        # 1. Load TabRecSet images (all three styles)
        images = self._load_tabrecset_images(file_id)
        
        # 2. Load TD annotations (table bounding box)
        table_bbox = self._load_td_annotation(file_id)
        
        # 3. Load TSR_TCR annotations (cells + structure)
        cells, structure = self._load_tsr_tcr_annotation(file_id)
        
        # 4. Load Tencent OCR annotations (text)
        text_annotations = self._load_tencent_ocr(file_id)
        
        # 5. Apply transforms
        if self.transform:
            images = self.transform(images)
        
        return {
            'file_id': file_id,
            'image': images,
            'table_bbox': torch.tensor(table_bbox, dtype=torch.float32) if table_bbox else None,
            'cells': cells,
            'structure': structure,
            'text': text_annotations,
        }
    
    def _load_tabrecset_images(self, file_id: str) -> torch.Tensor:
        """
        Load TabRecSet images (all three styles).
        
        Returns:
            Tensor of shape (3, H, W) or (1, H, W) depending on use_all_styles
        """
        images = []
        
        if self.use_all_styles:
            # Load all three styles
            for style in ['all_line', 'no_line', 'three_line']:
                img_path = os.path.join(self.image_dirs[style], f"{file_id}.jpg")
                if os.path.exists(img_path):
                    img = Image.open(img_path).convert('RGB')
                    img = img.resize(self.target_size)
                    images.append(np.array(img).transpose(2, 0, 1) / 255.0)
                else:
                    # If image doesn't exist, use a black image
                    images.append(np.zeros((3, *self.target_size)))
            
            # Stack all three images along channel dimension
            # Result: (9, H, W) if all three styles exist
            return torch.tensor(np.concatenate(images, axis=0), dtype=torch.float32)
        else:
            # Load only all_line style
            img_path = os.path.join(self.image_dirs['all_line'], f"{file_id}.jpg")
            if os.path.exists(img_path):
                img = Image.open(img_path).convert('RGB')
                img = img.resize(self.target_size)
                img = np.array(img).transpose(2, 0, 1) / 255.0
            else:
                img = np.zeros((3, *self.target_size))
            
            return torch.tensor(img, dtype=torch.float32)
    
    def _load_td_annotation(self, file_id: str) -> List[float]:
        """
        Load Table Detection annotation.
        
        Returns:
            [x1, y1, x2, y2] bounding box (normalized)
        """
        td_path = os.path.join(self.td_annotations_dir, f"{file_id}.json")
        
        if not os.path.exists(td_path):
            return [0.0, 0.0, 1.0, 1.0]  # Default to full image
        
        with open(td_path, 'r') as f:
            data = json.load(f)
        
        # Get polygon points from the first shape
        shapes = data.get('shapes', [])
        if not shapes:
            return [0.0, 0.0, 1.0, 1.0]
        
        points = shapes[0].get('points', [])
        if not points:
            return [0.0, 0.0, 1.0, 1.0]
        
        # Convert polygon to bounding box
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        
        x1, x2 = min(xs), max(xs)
        y1, y2 = min(ys), max(ys)
        
        # Normalize to [0, 1]
        # Use image dimensions from annotation or default 512
        img_height = 512  # Default
        img_width = 512   # Default
        
        # Try to get actual image size (if available in annotation)
        # Otherwise, use normalized coordinates
        x1_norm = x1 / img_width
        x2_norm = x2 / img_width
        y1_norm = y1 / img_height
        y2_norm = y2 / img_height
        
        return [x1_norm, y1_norm, x2_norm, y2_norm]
    
    def _load_tsr_tcr_annotation(self, file_id: str) -> Tuple[List[Dict], Dict]:
        """
        Load Table Structure Recognition + Content Recognition annotations.
        
        Returns:
            cells: List of cell annotations
            structure: {'rows': int, 'cols': int}
        """
        tsr_tcr_path = os.path.join(self.tsr_tcr_annotations_dir, f"{file_id}.json")
        
        if not os.path.exists(tsr_tcr_path):
            return [], {'rows': 0, 'cols': 0}
        
        with open(tsr_tcr_path, 'r') as f:
            data = json.load(f)
        
        shapes = data.get('shapes', [])
        cells = []
        rows = set()
        cols = set()
        
        for shape in shapes:
            label = shape.get('label', '')
            points = shape.get('points', [])
            
            # Parse label: "row-col-rowSpan-colSpan-"
            parts = label.split('-')
            if len(parts) >= 4:
                try:
                    row = int(parts[0]) - 1  # Convert to 0-indexed
                    col = int(parts[1]) - 1
                    row_span = int(parts[2]) if parts[2] else 1
                    col_span = int(parts[3]) if parts[3] else 1
                    
                    rows.add(row)
                    cols.add(col)
                    
                    # Convert polygon to bounding box
                    if points:
                        xs = [p[0] for p in points]
                        ys = [p[1] for p in points]
                        bbox = [min(xs), min(ys), max(xs), max(ys)]
                        
                        cells.append({
                            'row': row,
                            'col': col,
                            'row_span': row_span,
                            'col_span': col_span,
                            'bbox': bbox,
                        })
                except (ValueError, IndexError):
                    continue
        
        return cells, {'rows': max(rows) + 1 if rows else 0, 'cols': max(cols) + 1 if cols else 0}
    
    def _load_tencent_ocr(self, file_id: str) -> List[Dict]:
        """
        Load Tencent OCR annotations.
        
        Returns:
            List of text annotations with bounding boxes
        """
        tencent_path = os.path.join(self.tencent_ocr_dir, f"{file_id}.json")
        
        if not os.path.exists(tencent_path):
            return []
        
        with open(tencent_path, 'r') as f:
            data = json.load(f)
        
        shapes = data.get('shapes', [])
        annotations = []
        
        for shape in shapes:
            points = shape.get('points', [])
            # Extract text from shape if available
            # (Tencent OCR may have text in a different field)
            
            if points:
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                bbox = [min(xs), min(ys), max(xs), max(ys)]
                
                annotations.append({
                    'bbox': bbox,
                    'text': '',  # Text will be extracted from the image separately
                })
        
        return annotations


def collate_fn(batch: List[Dict]) -> Dict[str, Any]:
    """
    Custom collate function for batching.
    """
    file_ids = [item['file_id'] for item in batch]
    images = torch.stack([item['image'] for item in batch])
    table_bboxes = torch.stack([item['table_bbox'] if item['table_bbox'] is not None else torch.zeros(4) for item in batch])
    
    return {
        'file_ids': file_ids,
        'images': images,
        'table_bboxes': table_bboxes,
        'cells': [item['cells'] for item in batch],
        'structure': [item['structure'] for item in batch],
        'text': [item['text'] for item in batch],
    }


# Example usage
if __name__ == "__main__":
    # Test the dataset
    dataset = TableRecognitionDataset(
        data_dir="/app/data",
        split="train",
        target_size=(512, 512),
        use_all_styles=True,
    )
    
    print(f"Dataset size: {len(dataset)}")
    
    # Get a sample
    sample = dataset[0]
    print(f"Sample keys: {sample.keys()}")
    print(f"Image shape: {sample['image'].shape}")
    print(f"Table bbox: {sample['table_bbox']}")
    print(f"Structure: {sample['structure']}")
    print(f"Number of cells: {len(sample['cells'])}")
    print(f"Text annotations: {len(sample['text'])}")
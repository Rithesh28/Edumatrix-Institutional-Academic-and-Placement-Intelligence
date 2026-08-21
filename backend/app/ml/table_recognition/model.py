"""
CNN + Transformer Model for Table Recognition

Model Architecture:
├── CNN Backbone: ResNet (Feature Extraction)
├── Transformer Encoder: 6 layers (Structure Understanding)
└── Decoder Heads:
    ├── Table Detection Head (Binary Classification)
    ├── Structure Recognition Head (Row/Col Detection)
    └── Content Recognition Head (OCR)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Dict, Any, Optional
import logging
from .config import config

logger = logging.getLogger(__name__)


class CNNBackbone(nn.Module):
    """CNN Backbone for feature extraction."""
    
    def __init__(
        self,
        backbone_name: str = "resnet50",
        pretrained: bool = True,
        freeze_backbone: bool = False,
        in_channels: int = 9,
    ):
        super().__init__()
        
        import torchvision.models as models
        
        # Select backbone
        if backbone_name == "resnet18":
            backbone = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None)
            self.out_channels = 512
        elif backbone_name == "resnet34":
            backbone = models.resnet34(weights=models.ResNet34_Weights.IMAGENET1K_V1 if pretrained else None)
            self.out_channels = 512
        elif backbone_name == "resnet50":
            backbone = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1 if pretrained else None)
            self.out_channels = 2048
        elif backbone_name == "resnet101":
            backbone = models.resnet101(weights=models.ResNet101_Weights.IMAGENET1K_V1 if pretrained else None)
            self.out_channels = 2048
        else:
            raise ValueError(f"Unsupported backbone: {backbone_name}")
        
        # Get the first conv layer
        first_conv = backbone.conv1
        
        # Create new conv layer with correct input channels
        new_conv = nn.Conv2d(
            in_channels,
            first_conv.out_channels,
            kernel_size=first_conv.kernel_size,
            stride=first_conv.stride,
            padding=first_conv.padding,
            bias=first_conv.bias is not None
        )
        
        # If pretrained, copy weights
        if pretrained:
            with torch.no_grad():
                orig_weights = first_conv.weight.data
                new_weights = torch.zeros(new_conv.weight.shape)
                new_weights[:, :3, :, :] = orig_weights
                for i in range(3, in_channels):
                    new_weights[:, i:i+1, :, :] = orig_weights[:, 0:1, :, :]
                new_conv.weight.data = new_weights
        
        backbone.conv1 = new_conv
        self.features = nn.Sequential(*list(backbone.children())[:-2])
        
        if freeze_backbone:
            for param in self.features.parameters():
                param.requires_grad = False
        
        logger.info(f"CNN Backbone: {backbone_name}, Input channels: {in_channels}, Output channels: {self.out_channels}")
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.features(x)


class PositionalEncoding(nn.Module):
    """Positional Encoding for Transformer."""
    
    def __init__(self, d_model: int, max_len: int = 5000):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-torch.log(torch.tensor(10000.0)) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, :x.size(1), :]


class TransformerEncoder(nn.Module):
    """Transformer Encoder for structure understanding."""
    
    def __init__(self, d_model: int = 512, nhead: int = 8, num_layers: int = 6, dim_feedforward: int = 2048, dropout: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.pos_encoder = PositionalEncoding(d_model)
        self.encoder_layers = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=dim_feedforward,
                dropout=dropout,
                activation='relu',
                batch_first=True,
            ),
            num_layers=num_layers,
        )
        self.layer_norm = nn.LayerNorm(d_model)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.pos_encoder(x)
        x = self.encoder_layers(x)
        x = self.layer_norm(x)
        return x


class TableDetectionHead(nn.Module):
    """Table Detection Head (Binary Classification)."""
    
    def __init__(self, input_dim: int = 512):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, 2),
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(x)


class StructureRecognitionHead(nn.Module):
    """Structure Recognition Head (Row/Col Detection)."""
    
    def __init__(self, input_dim: int = 512, max_rows: int = 50, max_cols: int = 30):
        super().__init__()
        self.max_rows = max_rows
        self.max_cols = max_cols
        self.row_head = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, max_rows),
        )
        self.col_head = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, max_cols),
        )
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.row_head(x), self.col_head(x)


class ContentRecognitionHead(nn.Module):
    """Content Recognition Head (OCR/Text Recognition)."""
    
    def __init__(self, input_dim: int = 512, vocab_size: int = 1000, max_seq_len: int = 100):
        super().__init__()
        self.max_seq_len = max_seq_len
        self.seq_head = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, vocab_size),
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.seq_head(x)


class TableRecognitionModel(nn.Module):
    """Complete Table Recognition Model."""
    
    def __init__(
        self,
        backbone_name: str = "resnet50",
        pretrained: bool = True,
        freeze_backbone: bool = False,
        transformer_layers: int = 6,
        attention_heads: int = 8,
        hidden_dim: int = 512,
        ffn_dim: int = 2048,
        dropout: float = 0.1,
        max_rows: int = 50,
        max_cols: int = 30,
        vocab_size: int = 1000,
        max_seq_len: int = 100,
    ):
        super().__init__()
        
        # 1. CNN Backbone
        self.backbone = CNNBackbone(
            backbone_name=backbone_name,
            pretrained=pretrained,
            freeze_backbone=freeze_backbone,
            in_channels=9,
        )
        
        # 2. Get backbone output channels
        self.backbone_out_channels = self.backbone.out_channels
        
        # 3. Projection layer (CNN output to transformer input)
        self.projection = nn.Conv2d(
            self.backbone_out_channels,  # ← Now uses correct channels
            hidden_dim,
            kernel_size=1,
        )
        
        # 4. Transformer Encoder
        self.transformer = TransformerEncoder(
            d_model=hidden_dim,
            nhead=attention_heads,
            num_layers=transformer_layers,
            dim_feedforward=ffn_dim,
            dropout=dropout,
        )
        
        # 5. Decoder Heads
        self.table_detection_head = TableDetectionHead(hidden_dim)
        self.structure_head = StructureRecognitionHead(hidden_dim, max_rows, max_cols)
        self.content_head = ContentRecognitionHead(hidden_dim, vocab_size, max_seq_len)
        
        logger.info(f"Model initialized with backbone: {backbone_name}")
        logger.info(f"  Transformer layers: {transformer_layers}")
        logger.info(f"  Hidden dimension: {hidden_dim}")
        logger.info(f"  Backbone output channels: {self.backbone_out_channels}")
    
    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        batch_size = x.size(0)
        
        # 1. CNN Backbone
        features = self.backbone(x)
        
        # 2. Projection
        features = self.projection(features)
        
        # 3. Flatten spatial dimensions
        b, d, h, w = features.shape
        features = features.permute(0, 2, 3, 1).reshape(b, h * w, d)
        
        # 4. Transformer Encoder
        features = self.transformer(features)
        
        # 5. Global average pooling
        global_features = features.mean(dim=1)
        
        # 6. Decoder Heads
        table_detection = self.table_detection_head(global_features)
        rows, cols = self.structure_head(global_features)
        text = self.content_head(global_features.unsqueeze(1))
        
        return {
            'table_detection': table_detection,
            'rows': rows,
            'cols': cols,
            'text': text,
        }
    
    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
    
    def print_summary(self):
        logger.info("=" * 50)
        logger.info("Model Summary")
        logger.info("=" * 50)
        logger.info(f"Total parameters: {self.count_parameters():,}")
        logger.info("=" * 50)


def create_model(use_pretrained: bool = True) -> TableRecognitionModel:
    """Create a new Table Recognition Model."""
    model = TableRecognitionModel(
        backbone_name=config.model.CNN_BACKBONE,
        pretrained=use_pretrained,
        freeze_backbone=False,
        transformer_layers=config.model.TRANSFORMER_LAYERS,
        attention_heads=config.model.ATTENTION_HEADS,
        hidden_dim=config.model.HIDDEN_DIM,
        ffn_dim=config.model.FFN_DIM,
        dropout=config.model.DROPOUT,
        max_rows=config.model.MAX_ROWS,
        max_cols=config.model.MAX_COLS,
    )
    model.print_summary()
    return model
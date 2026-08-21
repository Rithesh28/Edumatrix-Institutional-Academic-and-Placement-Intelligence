import sys
sys.path.insert(0, '/app')

import torch
from app.ml.table_recognition.dataset import TableRecognitionDataset
from app.ml.table_recognition.model import TableRecognitionModel

# Load one sample
dataset = TableRecognitionDataset(split='train', target_size=(256, 256))
sample = dataset[0]

# Create smaller model
model = TableRecognitionModel(
    backbone_name='resnet18',
    pretrained=True,
    transformer_layers=2,
    attention_heads=4,
    hidden_dim=256,
    ffn_dim=512,
)

print(f'Model parameters: {model.count_parameters():,}')
print(f'Input shape: {sample["image"].shape}')

# Forward pass
with torch.no_grad():
    output = model(sample['image'].unsqueeze(0))
    print('Forward pass successful!')
    print(f'Output keys: {list(output.keys())}')
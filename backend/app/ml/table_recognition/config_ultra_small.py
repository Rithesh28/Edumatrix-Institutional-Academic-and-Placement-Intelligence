from .config import *

DatasetConfig.BATCH_SIZE = 1
DatasetConfig.NUM_WORKERS = 0
DatasetConfig.IMAGE_SIZE = (64, 64)
TrainingConfig.EPOCHS = 2
ModelConfig.CNN_BACKBONE = 'resnet18'
ModelConfig.TRANSFORMER_LAYERS = 1
ModelConfig.HIDDEN_DIM = 64
ModelConfig.FFN_DIM = 128

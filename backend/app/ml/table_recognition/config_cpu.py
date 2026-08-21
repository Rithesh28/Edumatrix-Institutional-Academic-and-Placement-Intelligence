from .config import *

# Override for CPU training
DatasetConfig.BATCH_SIZE = 4
DatasetConfig.NUM_WORKERS = 0
TrainingConfig.EPOCHS = 5
ModelConfig.CNN_BACKBONE = 'resnet18'
ModelConfig.TRANSFORMER_LAYERS = 2
ModelConfig.HIDDEN_DIM = 256

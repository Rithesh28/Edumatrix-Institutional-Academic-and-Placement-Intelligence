from .config import config

# Override for small CPU training
config.dataset.BATCH_SIZE = 2
config.dataset.NUM_WORKERS = 0
config.dataset.IMAGE_SIZE = (128, 128)
config.training.EPOCHS = 3
config.model.CNN_BACKBONE = 'resnet18'
config.model.TRANSFORMER_LAYERS = 2
config.model.HIDDEN_DIM = 128
config.model.FFN_DIM = 256

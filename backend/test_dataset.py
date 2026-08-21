import sys
sys.path.append('/app')
from app.ml.table_recognition.dataset import TableRecognitionDataset

print('Creating dataset...')
dataset = TableRecognitionDataset(
    data_dir='/app/data',
    split='train',
    target_size=(512, 512),
    use_all_styles=True,
)

print('Dataset loaded!')
print('Total samples:', len(dataset))
print('First 5 file IDs:', dataset.file_ids[:5])

# Get a sample
sample = dataset[0]
print('Sample keys:', list(sample.keys()))
print('Image shape:', sample['image'].shape)
print('Table bbox:', sample['table_bbox'])
print('Structure:', sample['structure'])
print('Number of cells:', len(sample['cells']))
print('Text annotations:', len(sample['text']))

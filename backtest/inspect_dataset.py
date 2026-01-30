import numpy as np

print("Loading dataset...")

data = np.load("data/december_2025_dataset.npz", allow_pickle=True)

print("Dataset loaded successfully.")
print("Number of keys:", len(data.files))
print("First 10 keys:")
print(data.files[:10])

sample_key = data.files[0]
sample = data[sample_key]

print("\nSample key:", sample_key)
print("Type:", type(sample))
print("Shape:", getattr(sample, "shape", None))
print("First row:")
print(sample[0])

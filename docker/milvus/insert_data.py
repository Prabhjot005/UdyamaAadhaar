from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
import random

# 1. Connect to Milvus
print("Connecting to Milvus...")
connections.connect("default", host="localhost", port="19530")

# 2. Define the Collection Schema (Equivalent to creating a table)
collection_name = "hello_milvus"
dim = 128  # Dimension of the vector embeddings

# Check if collection already exists and drop it if it does
if utility.has_collection(collection_name):
    utility.drop_collection(collection_name)

print(f"Creating collection: {collection_name}...")
# A collection needs a primary key, and a vector field.
fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
    FieldSchema(name="random_value", dtype=DataType.DOUBLE),
    FieldSchema(name="embeddings", dtype=DataType.FLOAT_VECTOR, dim=dim)
]
schema = CollectionSchema(fields, "A simple example collection")
collection = Collection(collection_name, schema)

# 3. Insert Data
print("Inserting data...")
num_entities = 3000
entities = [
    [i for i in range(num_entities)],  # field 'id'
    [float(random.randrange(-20, -10)) for _ in range(num_entities)],  # field 'random_value'
    [[random.random() for _ in range(dim)] for _ in range(num_entities)]  # field 'embeddings'
]

insert_result = collection.insert(entities)
print(f"Inserted {insert_result.insert_count} entities.")

# Flush data to make sure it's persisted and available for indexing/searching
collection.flush()

# 4. Create an Index (Required for efficient vector similarity search)
print("Creating index...")
index_params = {
    "metric_type": "L2", # L2 distance (Euclidean distance)
    "index_type": "IVF_FLAT",
    "params": {"nlist": 128}
}
collection.create_index(field_name="embeddings", index_params=index_params)
print("Index created successfully!")

# 5. Load the collection into memory before searching
collection.load()

# 6. Perform a Vector Similarity Search
print("Searching for similar vectors...")
search_vectors = [[random.random() for _ in range(dim)] for _ in range(2)] # 2 random query vectors
search_params = {
    "metric_type": "L2", 
    "params": {"nprobe": 10}
}

results = collection.search(
    data=search_vectors, 
    anns_field="embeddings", 
    param=search_params,
    limit=3, # return top 3 closest matches
    expr=None,
    output_fields=["random_value"] # Also return this metadata field
)

for i, result in enumerate(results):
    print(f"\nResults for query vector {i}:")
    for hit in result:
        print(f" - ID: {hit.id}, Distance: {hit.distance}, Random Value: {hit.entity.get('random_value')}")

print("\nDone!")

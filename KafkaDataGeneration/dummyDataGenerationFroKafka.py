import json
import time
import random
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    acks='all'
)

topic_name = "dlq_unvalidated_raw_data"

def generate_random_data():
    return {
        "name": f"User{random.randint(1, 1000)}",
        "address": f"Address {random.randint(1, 100)}",
        "pincode": str(random.randint(100000, 999999)),
        "city": random.choice(["Delhi", "Mumbai", "Bangalore", "Chennai"]),
        "gstin": f"22AAAAA{random.randint(1000, 9999)}A{random.randint(1, 9)}Z{random.randint(1, 9)}",
        "panNumber": f"AAAAA{random.randint(1000, 9999)}A",
        "departmentRecordId": str(random.randint(10000, 99999)),
        "departmentName": random.choice(["HR", "Finance", "IT", "Sales"]),
        "sourceName": random.choice(["SystemA", "SystemB", "Manual"])
    }

# Publish only one message for testing
data = generate_random_data()
print("Sending:", data)

future = producer.send(topic_name, value=data)

try:
    result = future.get(timeout=10)
    print(f"✅ Sent -> partition: {result.partition}, offset: {result.offset}")
except Exception as e:
    print("❌ Error:", e)
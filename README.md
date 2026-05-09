Follow the below steps to build your project after cloning master branch of Udyama Aadhaar : 

Step 1 : Navifate to microservices folder and create the docker containers :

cd Udyama Aadhaar\microservices
docker compose -f docker-compose.yml up -d

Step 2 : Now verify mOngo db and create Udyama database in Mongo DB from Mongo Express UI

Open http://localhost:8081/ with username 'admin' and password 'admin'.

Create a new database 'udyama'.

<img width="1366" height="853" alt="image" src="https://github.com/user-attachments/assets/1b46b754-24be-469d-a848-bbbcf3ef36b5" />

Step 3 : Open cmd and go inside the postgres db to create a new database 'udyama' in it. 

docker exec -it postgres /bin/bash
root@6b496d66ef1e:/# psql -U admin -d postgres
postgres=# CREATE DATABASE udyama;

New database 'Udyama' should be created.

We can verify the same using pgadmin ui : http://localhost:5050/

Step 4 : Also verify the milvus db by opening its Milvis-attu GUI interface using the link http://localhost:8000/#/

Step 5 : Set up kafka and create the required kafka topics using the following commands in cmd : 

docker exec -it kafka-broker /opt/kafka/bin/kafka-topics.sh --create --topic unvalidated_raw_data --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
docker exec -it kafka-broker /opt/kafka/bin/kafka-topics.sh --create --topic dlq_unvalidated_raw_data --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
docker exec -it kafka-broker /opt/kafka/bin/kafka-topics.sh --create --topic valid_department_records  --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
docker exec -it kafka-broker /opt/kafka/bin/kafka-topics.sh --create --topic unvalidated_events --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
docker exec -it kafka-broker /opt/kafka/bin/kafka-topics.sh --create --topic dlq_unvalidated_events --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
docker exec -it kafka-broker /opt/kafka/bin/kafka-topics.sh --create --topic valid_events  --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1

Step 6 : To setup kafka connect, go inside the terminal and install the mongodb connector using the following commands : 

docker exec -it connect /bin/bash
confluent-hub install --no-prompt mongodb/kafka-connect-mongodb:1.9.0

Now restart the connect container and open the below url to verify whether mongo db sink and source connectors are installed : 

Also run the following command in cmd to create and configure a sink connector : 

curl -X POST http://localhost:8083/connectors ^
  -H "Content-Type: application/json" ^
  -H "Accept: application/json" ^
  -d "{\"name\": \"unvalidated_raw_data_sink\", \"config\": {\"connector.class\": \"com.mongodb.kafka.connect.MongoSinkConnector\", \"topics\": \"unvalidated_raw_data\", \"connection.uri\": \"mongodb://admin:admin@mongodb:27017\", \"database\": \"udyama\", \"collection\": \"unvalidated_department_data\", \"key.converter\": \"org.apache.kafka.connect.storage.StringConverter\", \"value.converter\": \"org.apache.kafka.connect.json.JsonConverter\", \"value.converter.schemas.enable\": \"false\", \"tasks.max\": \"1\", \"errors.tolerance\": \"all\", \"errors.log.enable\": \"true\", \"errors.deadletterqueue.topic.name\": \"dlq_unvalidated_raw_data\"}}"

You can verify the status of the connector using the following link. It should be RUNNING : 
http://localhost:8083/connectors/unvalidated_raw_data_sink/status

Step 7 : Open the udyama_aadhaar_admin_app using the following link :

http://localhost:3003/

<img width="1570" height="724" alt="image" src="https://github.com/user-attachments/assets/79fd48be-d07e-4de5-9484-e32195f08ff7" />

Step 8 : Verify your validation service with below link : 

http://localhost:8010/hello

It should display "hello world"

If there are any issue, you can try restarting the container.

Step 9 : Verify the ubid_engine_core_service using the link http://localhost:8006/

It should display "{"message":"UBID Engine Core Service is running!"}"

If the container is not in healthy state or the link is not working, try restarting the container and then hit the link. Since it has dependency on Postgress and milvus, it could be possible that when these microservices containers were created, their dependent Databases were not yet and running. So restarting them will resolve the issue.

Step 10 : Similarly verify event_engine_core_service using the following link : 
http://localhost:8008/

It should display {"message":"Event Engine Core Service is running!"}.

Now all our components of the project are up and running. 

Test deoartment business records and test event records are stored in Udyama Aadhaard\KafkaDataGeneration\unverified_raw_test_data and Udyama Aadhaard\KafkaDataGeneration\unverified_test_event_data files. 

Replace it with your own data in json format and run the following commands to stream the data : 

python KafkaDataGeneration/Kafka_dummy_data_streaming --mode raw-data
python KafkaDataGeneration/Kafka_dummy_data_streaming --mode events

Resulting UBIDs can be obtained from the UBID master dashboard and UBID status dashboard.

UBID Master : 

<img width="1560" height="812" alt="image" src="https://github.com/user-attachments/assets/bd777a52-0b88-4009-a082-69039e19bf50" />

Event Master : 

<img width="1516" height="800" alt="image" src="https://github.com/user-attachments/assets/fa90e05f-6e77-43c1-ba97-f93485362265" />

UBID Status :

<img width="1570" height="756" alt="image" src="https://github.com/user-attachments/assets/9a3cde89-2a26-40c2-bf04-2ab8500f3009" />

Review Dashboards : 

<img width="1587" height="781" alt="image" src="https://github.com/user-attachments/assets/268b3d8c-5e58-4006-80b1-310336095583" />

Event Review Dashboard : 

<img width="1593" height="762" alt="image" src="https://github.com/user-attachments/assets/8bab3ec5-b122-4bc5-8d73-de835ff68410" />





docker compose run --rm workload-generator python workload_generator.py \
    --bootstrap-servers kafka1:9092,kafka2:9093,kafka3:9094 \
    --workload real_time \
    --duration 1800 \
    --total-messages 500000






docker compose run --rm -d workload-generator \
    --bootstrap-servers kafka1:9092,kafka2:9093,kafka3:9094 \
    --workload batch \
    --duration 3600 \
    --total-messages 1000000 \
    --batch-size 20000

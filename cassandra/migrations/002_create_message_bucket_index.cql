CREATE TABLE IF NOT EXISTS discord_messages.message_buckets_by_channel (
    channel_id uuid,
    bucket_date date,
    PRIMARY KEY (channel_id, bucket_date)
) WITH CLUSTERING ORDER BY (bucket_date DESC);
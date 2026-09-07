CREATE KEYSPACE IF NOT EXISTS discord_messages
WITH replication = {
    'class': 'NetworkTopologyStrategy',
    'datacenter1': 1
};

CREATE TABLE IF NOT EXISTS discord_messages.messages_by_channel_bucket (
    channel_id uuid,
    bucket_date date,
    created_at timestamp,
    message_id uuid,
    author_id uuid,
    message_content text,
    attachment_ids list<uuid>,
    edited_at timestamp,
    PRIMARY KEY (
        (channel_id, bucket_date),
        created_at,
        message_id
    )
) WITH CLUSTERING ORDER BY (
    created_at DESC,
    message_id DESC
);

DROP TABLE IF EXISTS discord_messages.message;
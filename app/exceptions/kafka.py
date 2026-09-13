class KafkaPublishError(Exception):
    """Raised when a message cannot be confirmed as published to Kafka."""
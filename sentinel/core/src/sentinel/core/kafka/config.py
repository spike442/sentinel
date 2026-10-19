from sentinel.core.config.settings import KafkaClientSettings
from sentinel.core.kafka.contracts import KafkaTopic


def client_config(settings: KafkaClientSettings) -> dict[str, str]:
    password = settings.kafka_password.get_secret_value()
    return {
        "bootstrap.servers": settings.kafka.bootstrap_servers,
        "security.protocol": settings.kafka.security_protocol,
        "sasl.mechanisms": settings.kafka.sasl_mechanisms,
        "sasl.username": settings.kafka_username,
        "sasl.password": password,
    }


def topic_name(settings: KafkaClientSettings, topic: KafkaTopic) -> str:
    return settings.kafka.topics[topic]

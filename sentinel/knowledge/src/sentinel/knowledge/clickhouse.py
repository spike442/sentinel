import clickhouse_connect
from pydantic import SecretStr
from sentinel.knowledge.config import ClickHouseConfig


class ClickHouse:
    def __init__(self, config: ClickHouseConfig, password: SecretStr):
        secret = password.get_secret_value()
        self.client = clickhouse_connect.get_client(
            host=config.host,
            port=config.port,
            database=config.database,
            username=config.user,
            password=secret,
            autogenerate_session_id=False,
            settings={"async_insert": 0},
        )

    def query(self, sql: str, parameters: dict | None = None) -> list[dict]:
        result = self.client.query(sql, parameters=parameters)
        rows = result.named_results()
        return list(rows)

    def command(self, sql: str) -> None:
        self.client.command(sql)

    def insert(self, table: str, rows: list[list], columns: list[str]) -> None:
        if rows:
            self.client.insert(table, rows, column_names=columns)

    def close(self) -> None:
        self.client.close()

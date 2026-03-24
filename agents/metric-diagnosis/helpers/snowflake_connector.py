"""
Minimal Snowflake connector for the metric-diagnosis agent.

Reads credentials from a YAML config file and returns query results
as pandas DataFrames. Caches the connection within a Python session
so externalbrowser (SSO) authentication fires only once.

Usage:
    from helpers.snowflake_connector import SnowflakeConnector

    conn = SnowflakeConnector.from_config("config/snowflake_config.yaml")
    df = conn.query("SELECT 1 AS test")
    print(df)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

# Module-level connection cache — keyed by (account, user, authenticator).
_CONNECTION_CACHE: dict = {}


class SnowflakeConnector:
    """Thin wrapper around snowflake-connector-python for this agent.

    Args:
        account: Snowflake account identifier (e.g. 'ab12345.us-east-1').
        user: Snowflake username / email.
        warehouse: Snowflake virtual warehouse name.
        database: Default database (queries may override with full paths).
        schema: Default schema.
        role: Snowflake role to assume.
        authenticator: Authentication method ('externalbrowser' for SSO,
            or 'snowflake' for password-based).
        password: Password (only used when authenticator='snowflake').
    """

    def __init__(
        self,
        account: str,
        user: str,
        warehouse: str,
        database: str = "",
        schema: str = "",
        role: str = "",
        authenticator: str = "externalbrowser",
        password: str = "",
    ):
        self._account = account
        self._user = user
        self._warehouse = warehouse
        self._database = database
        self._schema = schema
        self._role = role
        self._authenticator = authenticator
        self._password = password
        self._conn = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config_path: str | Path) -> "SnowflakeConnector":
        """Create a connector from a YAML config file.

        Args:
            config_path: Path to snowflake_config.yaml (see
                config/snowflake_config.yaml.example for format).

        Returns:
            SnowflakeConnector instance (not yet connected).
        """
        try:
            import yaml
        except ImportError:
            raise ImportError("pyyaml is required. pip install pyyaml")

        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Snowflake config not found: {path}\n"
                f"Copy config/snowflake_config.yaml.example to "
                f"config/snowflake_config.yaml and fill in your credentials."
            )

        with open(path) as f:
            cfg = yaml.safe_load(f)

        conn = cfg.get("connection", {})
        return cls(
            account=conn.get("account", ""),
            user=conn.get("user", ""),
            warehouse=conn.get("warehouse", ""),
            database=conn.get("database", ""),
            schema=conn.get("schema", ""),
            role=conn.get("role", ""),
            authenticator=conn.get("authenticator", "externalbrowser"),
            password=conn.get("password", ""),
        )

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> "SnowflakeConnector":
        """Establish (or reuse cached) Snowflake connection.

        Returns:
            self (for chaining).
        """
        try:
            import snowflake.connector
        except ImportError:
            raise ImportError(
                "snowflake-connector-python is required.\n"
                "pip install snowflake-connector-python"
            )

        cache_key = (self._account, self._user, self._authenticator)
        cached = _CONNECTION_CACHE.get(cache_key)

        if cached is not None:
            try:
                cached.cursor().execute("SELECT 1")
                self._conn = cached
                return self
            except Exception:
                _CONNECTION_CACHE.pop(cache_key, None)

        kwargs = {
            "account": self._account,
            "user": self._user,
            "warehouse": self._warehouse,
        }
        if self._database:
            kwargs["database"] = self._database
        if self._schema:
            kwargs["schema"] = self._schema
        if self._role:
            kwargs["role"] = self._role
        if self._authenticator == "externalbrowser":
            kwargs["authenticator"] = "externalbrowser"
        elif self._password:
            kwargs["password"] = self._password

        self._conn = snowflake.connector.connect(**kwargs)
        _CONNECTION_CACHE[cache_key] = self._conn
        return self

    def close(self) -> None:
        """Release connection reference (cached connection stays alive)."""
        self._conn = None

    def __enter__(self) -> "SnowflakeConnector":
        return self.connect()

    def __exit__(self, *_) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------

    def query(self, sql: str) -> pd.DataFrame:
        """Execute SQL and return results as a DataFrame.

        Args:
            sql: Snowflake SQL query string.

        Returns:
            pandas.DataFrame with query results.
        """
        if self._conn is None:
            self.connect()

        cur = self._conn.cursor()
        try:
            cur.execute(sql)
            data = cur.fetchall()
            cols = [desc[0].lower() for desc in cur.description]
            return pd.DataFrame(data, columns=cols)
        finally:
            cur.close()

    def test(self) -> bool:
        """Run a lightweight probe. Returns True if connected."""
        try:
            df = self.query("SELECT 1 AS ok")
            return df.iloc[0, 0] == 1
        except Exception:
            return False

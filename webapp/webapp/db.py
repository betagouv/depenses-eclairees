import pandas as pd
import streamlit as st
from sqlalchemy import text


def get_conn():
    return st.connection("default", type="sql")


def init_db():
    with get_conn().connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                key varchar PRIMARY KEY NOT NULL ,
                counter integer NOT NULL,
                expiry timestamp
            );
        """))
        conn.commit()


def list_attachments_by_ej_id(ej_id: str) -> pd.DataFrame:
    conn = get_conn()
    return conn.query(
        "select * from attachments where num_ej = :num_ej",
        params={"num_ej": ej_id},
        ttl=1,
    )

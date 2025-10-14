import logging

import streamlit as st

from webapp.oauth import init_oauth
from webapp.config import init_config, get as config_get
from webapp.db import init_db, list_attachments_by_ej_id
from webapp.rate_limits import check_rate_limit
from webapp.permissions import user_can_view_ej


logger = logging.getLogger(__name__)


init_config()
init_oauth()
init_db()


st.set_page_config(
    page_title="Dépenses Éclairées",
    page_icon="👋",
)


if not st.user.is_logged_in:
    st.title("Dépenses Éclairées")
    st.button("Se connecter", on_click=st.login, args=["auth0"])
    is_proconnect_allowed = config_get("PROCONNECT_ALLOWED") == "1"
    is_proconnect_enabled = st.query_params.get("proconnect") == "1"
    if is_proconnect_allowed and is_proconnect_enabled:
        st.button("ProConnect", on_click=st.login, args=["proconnect"])
    st.stop()


st.markdown(f"Utilisateur : {st.user.given_name} ({st.user.email})")
st.button("Se déconnecter", on_click=st.logout)

st.title("Dépenses Éclairées")


ej_id = st.text_input("Numéro d'engagement juridique", placeholder="10123...")


if st.button("Chercher") and ej_id:
    RATE_LIMIT = int(config_get('RATE_LIMIT', '200'))
    if not check_rate_limit(f'{st.user.sub}-search', RATE_LIMIT):
        logger.warning(
            f"RateLimit: User {st.user.email} search request exceeded limit of {RATE_LIMIT} requests")
        st.write("Limite de requêtes atteinte. Veuillez réessayer demain.")
    else:
        df_attachments = list_attachments_by_ej_id(ej_id)
        df_attachments.sort_values(by=["classification", "filename"], inplace=True)
        if df_attachments.empty:
            st.write("Aucun résultat")
        elif not user_can_view_ej(st.user, ej_id):
            logger.warning(f"PermissionDenied: User {st.user.email} cannot view EJ {ej_id}")
            st.write("Aucun résultat")
        else:
            st.subheader(f"EJ {ej_id}")
            df_processed = df_attachments[df_attachments.llm_response.notna()]
            df_not_processed = df_attachments[df_attachments.llm_response.isna()]
            for _, doc in df_processed.iterrows():
                with st.expander(f"[{doc.classification}] {doc.filename}"):
                    st.table(doc.llm_response)

            with st.expander("Non traités"):
                for _, doc in df_not_processed.iterrows():
                    st.write(f"[{doc.classification}] {doc.filename}")

            # Inject custom css to prevent first column from wrapping
            st.write('''<style>
                [data-testid="stTableStyledTable"] th {
                    white-space: nowrap;
                }
                </style>''', unsafe_allow_html=True)

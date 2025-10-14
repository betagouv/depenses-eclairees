from typing import Any

import tornado
from authlib.jose import JsonWebToken, jwt
from streamlit.web.server.oidc_mixin import TornadoOAuth2App, TornadoOAuth
import requests


class MyOauth2App(TornadoOAuth2App):
    def authorize_access_token(
        self, request_handler: tornado.web.RequestHandler, **kwargs: Any
    ) -> dict[str, Any]:
        token = super().authorize_access_token(request_handler, **kwargs)
        userinfo_endpoint = self.server_metadata["userinfo_endpoint"]
        resp = requests.get(userinfo_endpoint, headers={
            "Authorization": f"Bearer {token['access_token']}"
        })
        if 'auth0.com' in token["userinfo"]["iss"]:
            userinfo = resp.json()
            userinfo["given_name"] = userinfo["nickname"]
        else:
            content = resp.content
            # From OpenIDMixin.parse_id_token
            alg_values = self.server_metadata.get("userinfo_signing_alg_values_supported")
            if alg_values:
                _jwt = JsonWebToken(alg_values)
            else:
                _jwt = jwt
            load_key = self.create_load_key()
            claims = _jwt.decode(
                content,
                key=load_key,
            )
            claims.validate(leeway=120)
            userinfo = claims
        token["token_userinfo"] = token["userinfo"]
        token["userinfo"] = userinfo
        return token


def init_oauth():
    TornadoOAuth.oauth2_client_cls = MyOauth2App



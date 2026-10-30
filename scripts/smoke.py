"""Post-deployment smoke test for TCMS (standard library only).

Exercises the public health endpoint, portal pages, API authentication, token
revocation and a role-scoped API read. Run against a deployed staging or
production URL after cut-over.

Examples::

    python scripts/smoke.py --base-url https://tcms.example.com
    python scripts/smoke.py --base-url https://staging.example.com --insecure \
        --api-username demo_accounts --api-password demo12345 \
        --portal-email demo_learner@tcms.local --portal-password demo12345
"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
from http.cookiejar import CookieJar
from urllib import error, parse, request

DEFAULT_TIMEOUT = 15.0
PUBLIC_PATHS = [
    "/api/v1/health/",
    "/portal/",
    "/portal/register/",
    "/portal/registered/",
    "/portal/login/",
    "/portal/resend-verification/email/",
]


class Response:
    def __init__(self, status: int, headers, body: str):
        self.status_code = status
        self.headers = headers
        self.body = body

    @property
    def text(self) -> str:
        return self.body

    def json(self):
        return json.loads(self.body or "{}")


class NoRedirect(request.HTTPRedirectHandler):
    """Return 3xx responses to the caller instead of following them."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Smoke:
    def __init__(self, base_url: str, timeout: float, verify: bool):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.failures: list[str] = []
        self.jar = CookieJar()
        context = ssl.create_default_context()
        if not verify:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        self.opener = request.build_opener(
            request.HTTPCookieProcessor(self.jar),
            NoRedirect(),
            request.HTTPSHandler(context=context),
        )

    def request(self, method: str, path: str, *, json_body=None, form=None, headers=None):
        headers = dict(headers or {})
        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
        elif form is not None:
            data = parse.urlencode(form).encode("utf-8")
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        req = request.Request(
            f"{self.base_url}{path}", data=data, headers=headers, method=method
        )
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                return Response(
                    response.status, response.headers, response.read().decode(errors="replace")
                )
        except error.HTTPError as exc:
            return Response(exc.code, exc.headers, exc.read().decode(errors="replace"))
        except error.URLError as exc:
            raise RuntimeError(f"{method} {path} failed: {exc.reason}") from exc

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        if ok:
            print(f"PASS  {name}")
        else:
            self.failures.append(name)
            print(f"FAIL  {name}{': ' + detail if detail else ''}")

    def public_pages(self) -> None:
        for path in PUBLIC_PATHS:
            response = self.request("GET", path)
            self.check(f"GET {path}", response.status_code == 200, f"HTTP {response.status_code}")
        response = self.request("GET", "/api/v1/health/")
        try:
            body = response.json()
        except ValueError:
            body = {}
        self.check(
            "health payload",
            body.get("status") == "ok",
            f"unexpected body {response.text[:120]!r}",
        )

    def auth_required(self) -> None:
        response = self.request("GET", "/api/v1/companies/")
        self.check(
            "unauthenticated API read is 401",
            response.status_code == 401,
            f"HTTP {response.status_code}",
        )
        response = self.request("GET", "/portal/dashboard/")
        self.check(
            "unauthenticated portal dashboard redirects",
            response.status_code in (301, 302),
            f"HTTP {response.status_code}",
        )

    def api_flow(self, username: str, password: str) -> None:
        response = self.request(
            "POST",
            "/api/v1/auth/login",
            json_body={"username": username, "password": password},
        )
        self.check("API login", response.status_code == 200, f"HTTP {response.status_code}")
        if response.status_code != 200:
            return
        token = response.json().get("token", "")
        self.check("API login returns token", bool(token))
        if not token:
            return
        headers = {"Authorization": f"Token {token}"}
        response = self.request("GET", "/api/v1/companies/", headers=headers)
        self.check("API token read", response.status_code == 200, f"HTTP {response.status_code}")
        response = self.request("POST", "/api/v1/auth/logout", headers=headers)
        self.check("API logout", response.status_code == 204, f"HTTP {response.status_code}")
        response = self.request("GET", "/api/v1/companies/", headers=headers)
        self.check(
            "revoked token is rejected",
            response.status_code == 401,
            f"HTTP {response.status_code}",
        )

    def portal_flow(self, email: str, password: str) -> None:
        login_url = f"{self.base_url}/portal/login/"
        response = self.request("GET", "/portal/login/")
        self.check("portal login page", response.status_code == 200, f"HTTP {response.status_code}")
        csrf = next((cookie.value for cookie in self.jar if cookie.name == "csrftoken"), "")
        if not csrf:
            self.check("portal CSRF cookie", False, "csrftoken cookie missing")
            return
        response = self.request(
            "POST",
            "/portal/login/",
            form={"csrfmiddlewaretoken": csrf, "email": email, "password": password},
            headers={"Referer": login_url, "Origin": self.base_url},
        )
        self.check("portal login", response.status_code == 302, f"HTTP {response.status_code}")
        response = self.request("GET", "/portal/dashboard/")
        self.check("portal dashboard", response.status_code == 200, f"HTTP {response.status_code}")

    def docs(self) -> None:
        response = self.request("GET", "/api/schema/")
        self.check("API schema", response.status_code == 200, f"HTTP {response.status_code}")


def main() -> int:
    parser = argparse.ArgumentParser(description="TCMS post-deployment smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--insecure", action="store_true", help="skip TLS verification")
    parser.add_argument("--api-username")
    parser.add_argument("--api-password")
    parser.add_argument("--portal-email")
    parser.add_argument("--portal-password")
    parser.add_argument("--check-docs", action="store_true", help="assert /api/schema/ is exposed")
    args = parser.parse_args()

    smoke = Smoke(args.base_url, args.timeout, verify=not args.insecure)
    try:
        smoke.public_pages()
        smoke.auth_required()
        if args.api_username and args.api_password:
            smoke.api_flow(args.api_username, args.api_password)
        if args.portal_email and args.portal_password:
            smoke.portal_flow(args.portal_email, args.portal_password)
        if args.check_docs:
            smoke.docs()
    except RuntimeError as exc:
        print(f"FAIL  {exc}")
        return 1

    if smoke.failures:
        print(f"\n{len(smoke.failures)} check(s) failed: {', '.join(smoke.failures)}")
        return 1
    print("\nAll smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

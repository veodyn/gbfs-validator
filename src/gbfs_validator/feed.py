"""Port of upstream gbfs.js: discover a feed, fetch its files, report on them.

Structure and quirks follow the JS closely, including the ones that look like
bugs. Where upstream leaves a value undefined, we omit the key, because that
is what JSON.stringify does on the other side.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from gbfs_validator.conditionals import conditional_context, find_type, partials_for
from gbfs_validator.discovery import feed_entries
from gbfs_validator.feedhelpers import is_js_object, load_schema
from gbfs_validator.fetch import Fetcher, FetchError
from gbfs_validator.jstruth import truthy
from gbfs_validator.jsvalues import interpolate, member, optional
from gbfs_validator.results import (
    count_errors,
    file_has_errors,
    files_have_errors,
    total_errors_count,
)
from gbfs_validator.validate import validate_file
from gbfs_validator.version import __version__
from gbfs_validator.versions import files_for, gbfs_required

# Upstream's /gbfs.json$/ leaves the dot unescaped, so it also matches
# "gbfs_json" or "gbfsXjson" (gbfs.js:424).
_AUTODISCOVERY = re.compile(r"gbfs.json\Z")


class GBFS:
    def __init__(
        self,
        url: str,
        docked: bool = False,
        freefloating: bool = False,
        version: str | None = None,
        auth: dict[str, Any] | None = None,
        fetcher: Fetcher | None = None,
    ) -> None:
        if not url:
            raise ValueError("Missing URL")
        self.url = url
        self.docked = docked
        self.freefloating = freefloating
        self.version = version
        self.auth = auth or {}
        self.fetcher = fetcher or Fetcher(auth=self.auth)
        self.auto_discovery: dict[str, Any] | None = None

    def _required_for(self, version: Any) -> bool:
        return gbfs_required(interpolate(version)) if truthy(version) else False

    def _missing_gbfs(self, url: str) -> dict[str, Any]:
        return {
            "url": url,
            "recommended": True,
            "required": self._required_for(self.version),
            "errors": False,
            "exists": False,
            "file": "gbfs.json",
            "hasErrors": False,
        }

    def check_autodiscovery(self) -> dict[str, Any]:
        try:
            body = self.fetcher.get_json(self.url)
            if not is_js_object(body):
                return self.alternative_autodiscovery(urljoin(self.url, "gbfs.json"))
            return self._autodiscovery_result(body, self.url, fallback_version=True)
        except Exception:  # noqa: BLE001 - got's .catch() swallows the whole chain
            if not _AUTODISCOVERY.search(self.url):
                return self.alternative_autodiscovery(urljoin(self.url, "gbfs.json"))
            return self._missing_gbfs(self.url)

    def alternative_autodiscovery(self, url: str) -> dict[str, Any]:
        try:
            body = self.fetcher.get_json(url)
            if not is_js_object(body):
                return {
                    "recommended": True,
                    "required": self._required_for(self.version),
                    "errors": False,
                    "exists": False,
                    "file": "gbfs.json",
                    "hasErrors": False,
                    "url": None,
                }
            return self._autodiscovery_result(body, url, fallback_version=False)
        except Exception:  # noqa: BLE001 - got's .catch() swallows the whole chain
            return self._missing_gbfs(url)

    def _autodiscovery_result(self, body: Any, url: str, fallback_version: bool) -> dict[str, Any]:
        self.auto_discovery = body
        # `body.version` on a null body throws, and the caller's catch turns
        # that into a missing gbfs.json rather than validating null.
        detected = member(body, "version")
        validated = self.version or detected or "1.0"
        result = validate_file(load_schema(interpolate(validated), "gbfs"), body)
        # The direct path defaults a missing version to 1.0; the fallback path
        # reports it as-is (gbfs.js:353 against :403).
        reported = (detected or "1.0") if fallback_version else detected
        out: dict[str, Any] = {
            "schema": result["schema"],
            "errors": result["errors"],
            "url": url,
            "recommended": True,
            "required": self._required_for(validated),
            "exists": True,
            "file": "gbfs.json",
            "hasErrors": bool(result["errors"]),
        }
        if reported is not None:
            out["version"] = reported
        return out

    def get_file(self, file_type: str, required: bool) -> dict[str, Any]:
        if self.auto_discovery is None:
            return self._get_flat_file(file_type, required)

        version = self.version or member(self.auto_discovery, "version")
        data = member(self.auto_discovery, "data")
        return {
            "file": f"{file_type}.json",
            "body": [self._fetch_entry(e) for e in feed_entries(data, file_type, version)],
            "required": required,
            "type": file_type,
        }

    def _fetch_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if "lang" in entry:
            out["lang"] = entry["lang"]
        url = entry.get("url")
        if not url:
            return {"body": None, "exists": False, **out, "url": None}
        try:
            return {"body": self.fetcher.get_json(url), "exists": True, **out, "url": url}
        except FetchError:
            return {"body": None, "exists": False, **out, "url": url}

    def _get_flat_file(self, file_type: str, required: bool) -> dict[str, Any]:
        url = f"{self.url}/{file_type}.json"
        try:
            body = self.fetcher.get_json(url)
        except FetchError as exc:
            return {
                "file": f"{file_type}.json",
                "body": None,
                "required": required,
                "errors": str(exc) if required else None,
                "exists": False,
                "type": file_type,
            }
        return {
            "file": f"{file_type}.json",
            "body": body,
            "required": required,
            "exists": True,
            "type": file_type,
        }

    def validation_file(
        self,
        body: Any,
        version: str,
        file_type: str,
        required: bool,
        add_schema: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        schema = load_schema(version, file_type)
        if isinstance(body, list):
            languages = [
                {**entry, **validate_file(schema, entry.get("body"), add_schema)}
                for entry in body
                if truthy(entry.get("exists")) or truthy(entry.get("required"))
            ]
            return {
                "languages": languages,
                "required": required,
                "exists": all(lang.get("exists") for lang in languages) if languages else False,
                "file": f"{file_type}.json",
                "hasErrors": file_has_errors(languages, required),
            }
        return {
            "required": required,
            **validate_file(schema, body, add_schema),
            "exists": bool(body),
            "file": f"{file_type}.json",
            "url": f"{self.url}/{file_type}.json",
        }

    def get_files(self) -> dict[str, Any]:
        if self.auth.get("type") == "oauth_client_credentials_grant":
            self.fetcher.prime_oauth()

        gbfs_result = self.check_autodiscovery()
        if not truthy(gbfs_result.get("version")):
            summary: dict[str, Any] = {
                "gbfsResult": gbfs_result,
                "validatorVersion": __version__,
                "versionUnimplemented": True,
            }
            return {"summary": summary}

        version = self.version or gbfs_result["version"]
        wanted = files_for(interpolate(version), docked=self.docked, freefloating=self.freefloating)
        return {
            "summary": {},
            "gbfsResult": gbfs_result,
            "gbfsVersion": version,
            "files": [self.get_file(f["file"], f["required"]) for f in wanted],
        }

    def validation(self) -> dict[str, Any]:
        fetched = self.get_files()
        if fetched["summary"].get("versionUnimplemented"):
            return {"summary": fetched["summary"]}

        gbfs_result = fetched["gbfsResult"]
        # Every schema and partial path upstream builds is a template literal,
        # so a numeric version is rendered before it selects anything.
        version = interpolate(fetched["gbfsVersion"])
        files = fetched["files"]

        self._chase_manifest(files)
        context = conditional_context(files)

        results = [gbfs_result]
        for file in files:
            add_schema, required = partials_for(version, file, context)
            results.append(
                self.validation_file(file.get("body"), version, file["type"], required, add_schema)
            )

        counted = [{**file, "errorsCount": count_errors(file)} for file in results]
        return {
            "summary": {
                "validatorVersion": __version__,
                "version": {
                    "detected": gbfs_result.get("version"),
                    "validated": self.version or gbfs_result.get("version"),
                },
                "hasErrors": files_have_errors(results),
                "errorsCount": total_errors_count(counted),
            },
            "files": counted,
        }

    def _chase_manifest(self, files: list[dict[str, Any]]) -> None:
        system_information = find_type(files, "system_information")
        manifest_url = optional(system_information, "body", 0, "body", "data", "manifest_url")
        if not truthy(manifest_url):
            return
        try:
            manifest = self.fetcher.get_json(manifest_url)
        except FetchError:
            files.append(
                {
                    "url": manifest_url,
                    "recommended": True,
                    "required": True,
                    "errors": False,
                    "exists": False,
                    "file": "manifest.json",
                    "type": "manifest",
                    "hasErrors": False,
                }
            )
            return
        files.append(
            {
                "body": [{"body": manifest, "exists": True, "url": manifest_url}],
                "required": True,
                "type": "manifest",
            }
        )

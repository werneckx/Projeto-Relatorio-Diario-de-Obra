from __future__ import annotations

from pathlib import Path

from flask.templating import DispatchingJinjaLoader
from jinja2 import BaseLoader, TemplateNotFound
from jinja2.loaders import split_template_path


class FallbackEncodingLoader(BaseLoader):
    """Wraps the default loader and retries legacy Windows encodings on decode errors."""

    def __init__(self, inner_loader, encodings: tuple[str, ...] = ("utf-8", "cp1252", "latin-1")):
        self.inner_loader = inner_loader
        self.encodings = encodings

    def get_source(self, environment, template):
        try:
            return self.inner_loader.get_source(environment, template)
        except UnicodeDecodeError:
            return self._get_source_with_fallback(template)

    def list_templates(self):
        if hasattr(self.inner_loader, "list_templates"):
            return self.inner_loader.list_templates()
        return super().list_templates()

    def _get_source_with_fallback(self, template):
        for candidate in self._iter_candidate_files(template):
            raw = candidate.read_bytes()
            for encoding in self.encodings:
                try:
                    source = raw.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise

            mtime = candidate.stat().st_mtime

            def uptodate(path=candidate, expected_mtime=mtime):
                return path.is_file() and path.stat().st_mtime == expected_mtime

            return source, str(candidate), uptodate

        raise TemplateNotFound(template)

    def _iter_candidate_files(self, template):
        pieces = split_template_path(template)

        if isinstance(self.inner_loader, DispatchingJinjaLoader):
            for _srcobj, loader in self.inner_loader._iter_loaders(template):
                for candidate in self._iter_loader_searchpaths(loader, pieces):
                    yield candidate
            return

        for candidate in self._iter_loader_searchpaths(self.inner_loader, pieces):
            yield candidate

    @staticmethod
    def _iter_loader_searchpaths(loader, pieces):
        search_paths = getattr(loader, "searchpath", None)
        if not search_paths:
            return

        for base_path in search_paths:
            candidate = Path(base_path, *pieces)
            if candidate.is_file():
                yield candidate
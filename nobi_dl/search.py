from .common import ExtractorBase


class Searcher(ExtractorBase):
    def __init__(self, md=None, force_extractor=None):
        super().__init__(md)
        self.md = md
        self.force_extractor = force_extractor

    def get_all_searcher(self) -> list[dict]:
        searchers = []

        for extractor in self.gen_extractors(self.md):
            if not hasattr(extractor, "_real_search"):
                continue

            ie_name = getattr(extractor, "_IE_NAME", None)
            if not ie_name:
                continue

            searchers.append(
                {
                    "ie": extractor,
                    "name": ie_name,
                }
            )

        return searchers

    def search(self, query: str) -> dict:
        raw_result = self._raw_search(query)

        if not raw_result:
            return {
                "query": query,
                "total": 0,
                "best": None,
                "results": [],
            }

        ranked = self._rank_results(raw_result, query)

        return {
            "query": query,
            "total": len(ranked),
            "best": ranked[0] if ranked else None,
            "results": ranked,
        }

    def _rank_results(self, results, query):
        q = query.lower()

        def score(r):
            s = 0
            title = r.get("title", "").lower()

            if q in title:
                s += 50

            quality = r.get("quality") or []
            if "1080p" in quality:
                s += 20
            if "2160p" in quality:
                s += 30

            return s

        return sorted(results, key=score, reverse=True)

    def _raw_search(self, query: str):
        searchers = self.get_all_searcher()

        if self.force_extractor:
            searchers = [
                s
                for s in searchers
                if self.force_extractor.lower() in s["ie"].__class__.__name__.lower()
                or self.force_extractor.lower() in s["name"].lower()
            ]

            if not searchers:
                self.show_warning(
                    "The extractor doesn't support search or is not implemented yet. "
                    "Try --list-extractors"
                )
                return []

        results = []

        for s in searchers:
            ie = s["ie"]

            if getattr(ie, "_SEARCH", True) is False:
                self.show_warning(f"skipping {s['name']} (search disabled)")
                continue
            self.logger.set_ie(ie, "search")
            try:
                res = ie._real_search(query)
                if res:
                    results.extend(res)
            except Exception as e:
                self.write_debug(f"Search failed for {s['name']}: {e}")

        return results

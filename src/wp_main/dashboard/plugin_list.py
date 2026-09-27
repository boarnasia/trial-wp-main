from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from .. import plugins
from ..config import SITES, Site
from ..runner import Runner
from .data import read_site_env, sites_root
from .models import PluginInfo, SiteFetch, SitePlugin

STATUS_LABELS = {plugins.OK: "OK", plugins.NG: "NG", plugins.UNKNOWN: "不明"}


@dataclass(frozen=True)
class RefreshResult:
    succeeded: bool
    summary: str


def refresh(
    runner: Runner,
    sites: tuple[Site, ...] = SITES,
    *,
    fetch_site: Callable[[Runner, Site], plugins.SiteResult] = plugins.fetch_site,
    fetch_org: plugins.OrgFetcher = plugins.fetch_org,
) -> RefreshResult:
    parts, ok = [], True
    for site in sites:
        result = fetch_site(runner, site)
        now = timezone.now()
        with transaction.atomic():
            if result.error:
                ok = False
                parts.append(f"{site.id} 取得失敗")
                # 前回の一覧は残し、試行の結果だけを書き換える
                SiteFetch.objects.update_or_create(site_id=site.id, defaults={
                    "attempted_at": now, "succeeded": False, "error": result.error[:500],
                })
                continue
            SitePlugin.objects.filter(site_id=site.id).delete()
            SitePlugin.objects.bulk_create(
                SitePlugin(site_id=site.id, slug=item.slug, title=item.title[:300], version=item.version,
                           status=item.status)
                for item in result.plugins
            )
            SiteFetch.objects.update_or_create(site_id=site.id, defaults={
                "attempted_at": now, "succeeded": True, "error": "", "succeeded_at": now,
                "wp_version": result.wp_version or "",
            })
        parts.append(f"{site.id} {len(result.plugins)} 件")

    slugs = sorted(set(
        SitePlugin.objects.filter(status__in=plugins.QUERIED_STATUSES).values_list("slug", flat=True)
    ))
    fetched = 0
    for slug in slugs:
        info = fetch_org(slug)
        if info is None:
            continue
        fetched += 1
        PluginInfo.objects.update_or_create(slug=slug, defaults={
            "found": info.found, "name": info.name[:300], "requires": info.requires, "tested": info.tested,
            "fetched_at": timezone.now(),
        })
    if fetched < len(slugs):
        ok = False
    parts.append(f"wordpress.org {fetched}/{len(slugs)}")
    return RefreshResult(ok, "・".join(parts))


@dataclass(frozen=True)
class SiteColumn:
    id: str
    version: str | None
    major: int | None
    fetch: SiteFetch | None

    @property
    def fetched(self) -> bool:
        return bool(self.fetch and self.fetch.succeeded_at)


@dataclass(frozen=True)
class Cell:
    site: str
    version: str | None = None
    status: str = ""
    warning: str = ""

    @property
    def installed(self) -> bool:
        return self.version is not None


@dataclass
class Row:
    slug: str
    title: str
    url: str | None
    majors: list[tuple[int, str, str]] = field(default_factory=list)
    cells: list[Cell] = field(default_factory=list)

    @property
    def search_text(self) -> str:
        return f"{self.title} {self.slug}".lower()

    @property
    def site_ids(self) -> str:
        return " ".join(cell.site for cell in self.cells if cell.installed)

    @property
    def warned(self) -> bool:
        return any(cell.warning for cell in self.cells)


@dataclass(frozen=True)
class PluginTable:
    sites: list[SiteColumn]
    majors: list[int]
    rows: list[Row]
    fetched_at: datetime | None

    @property
    def empty(self) -> bool:
        return self.fetched_at is None


def site_version(site: Site, fetch: SiteFetch | None, base: Path) -> str | None:
    if fetch and fetch.wp_version:
        return fetch.wp_version
    # 取得前でも列を並べられるよう、サイト設定のイメージのタグを使う
    image = (read_site_env(site, base) or {}).get("WP_IMAGE", site.image)
    tag = image.rpartition(":")[2]
    return ".".join(map(str, plugins.parse_version(tag))) if plugins.parse_version(tag) else None


def build_table(sites: tuple[Site, ...] = SITES, base: Path | None = None) -> PluginTable:
    base = base or sites_root()
    fetches = {fetch.site_id: fetch for fetch in SiteFetch.objects.all()}
    columns = []
    for site in sites:
        version = site_version(site, fetches.get(site.id), base)
        parsed = plugins.parse_version(version)
        columns.append(SiteColumn(site.id, version, parsed[0] if parsed else None, fetches.get(site.id)))
    majors = sorted({column.major for column in columns if column.major is not None})

    installed: dict[str, dict[str, SitePlugin]] = {}
    for item in SitePlugin.objects.filter(site_id__in=[site.id for site in sites]):
        installed.setdefault(item.slug, {})[item.site_id] = item
    infos = {info.slug: info for info in PluginInfo.objects.filter(slug__in=list(installed))}

    rows = []
    for slug, by_site in installed.items():
        info = infos.get(slug)
        known = info is not None and info.found
        title = (info.name if known and info.name else None) or next(iter(by_site.values())).title
        row = Row(slug=slug, title=title, url=f"https://wordpress.org/plugins/{slug}/" if known else None)
        for major in majors:
            status = plugins.major_status(major, info.requires, info.tested) if known else plugins.UNKNOWN
            row.majors.append((major, status, STATUS_LABELS[status]))
        for column in columns:
            item = by_site.get(column.id)
            if item is None:
                row.cells.append(Cell(column.id))
                continue
            supported = (
                plugins.site_supported(column.version or "", info.requires, info.tested) if known else None
            )
            warning = f"{column.version} 非対応" if supported is False else ""
            row.cells.append(Cell(column.id, item.version, item.status, warning))
        rows.append(row)
    rows.sort(key=lambda row: row.title.lower())
    attempts = [fetch.attempted_at for fetch in fetches.values()]
    return PluginTable(columns, majors, rows, max(attempts) if attempts else None)

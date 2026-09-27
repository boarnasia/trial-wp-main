from django.db import models

MAX_OPERATIONS = 1000


class Operation(models.Model):
    command = models.CharField(max_length=32)
    options = models.JSONField(default=dict)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(db_index=True)
    exit_code = models.IntegerField()
    # migrate --auto は失敗しても終了コード 0 で終わるため、成否は終了コードと別に持つ
    succeeded = models.BooleanField()
    summary = models.CharField(max_length=500)

    class Meta:
        ordering = ["-finished_at", "-id"]

    def __str__(self) -> str:
        return f"{self.command} {self.finished_at:%Y-%m-%d %H:%M} {self.summary}"

    @classmethod
    def prune(cls, keep: int | None = None) -> int:
        keep = MAX_OPERATIONS if keep is None else keep
        stale = cls.objects.values_list("id", flat=True)[keep:]
        deleted, _ = cls.objects.filter(id__in=list(stale)).delete()
        return deleted


class SiteFetch(models.Model):
    """サイトごとの、プラグイン情報の最後の取得の試行。"""

    site_id = models.CharField(max_length=32, primary_key=True)
    attempted_at = models.DateTimeField()
    succeeded = models.BooleanField()
    error = models.CharField(max_length=500, blank=True)
    # 失敗しても前回の一覧を表示し続けるため、最後に成功したときの値を別に持つ
    succeeded_at = models.DateTimeField(null=True)
    wp_version = models.CharField(max_length=32, blank=True)


class SitePlugin(models.Model):
    site_id = models.CharField(max_length=32)
    slug = models.CharField(max_length=200)
    title = models.CharField(max_length=300)
    version = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=16)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["site_id", "slug"], name="unique_site_plugin")]


class PluginInfo(models.Model):
    """wordpress.org に載っている、プラグインの最新版の情報。"""

    slug = models.CharField(max_length=200, primary_key=True)
    found = models.BooleanField()
    name = models.CharField(max_length=300, blank=True)
    requires = models.CharField(max_length=32, blank=True)
    tested = models.CharField(max_length=32, blank=True)
    fetched_at = models.DateTimeField()

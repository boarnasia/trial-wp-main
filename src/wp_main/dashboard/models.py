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

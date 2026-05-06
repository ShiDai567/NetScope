import uuid

from django.db import models
from django.utils import timezone

from topology.models import NetworkNode


class PacketEvent(models.Model):
    class Protocol(models.TextChoices):
        TCP = "TCP", "TCP"
        UDP = "UDP", "UDP"
        ICMP = "ICMP", "ICMP"

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        DELAYED = "delayed", "Delayed"
        DROPPED = "dropped", "Dropped"

    packet_id = models.CharField(max_length=64, unique=True, db_index=True, blank=True)
    source_node = models.ForeignKey(
        NetworkNode,
        on_delete=models.CASCADE,
        related_name="source_packets",
    )
    destination_node = models.ForeignKey(
        NetworkNode,
        on_delete=models.CASCADE,
        related_name="destination_packets",
    )
    protocol = models.CharField(max_length=16, choices=Protocol.choices, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, db_index=True)
    payload_size = models.PositiveIntegerField()
    event_timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-event_timestamp", "-id"]
        indexes = [
            models.Index(fields=["event_timestamp", "status"]),
            models.Index(fields=["source_node", "destination_node", "event_timestamp"]),
        ]

    def save(self, *args, **kwargs):
        if not self.packet_id:
            self.packet_id = f"pkt_{uuid.uuid4().hex[:12]}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.packet_id} ({self.protocol})"

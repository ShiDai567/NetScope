from django.db import models


class NetworkNode(models.Model):
    class NodeType(models.TextChoices):
        SERVER = "server", "Server"
        CLIENT = "client", "Client"

    node_id = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(db_index=True)
    node_type = models.CharField(max_length=16, choices=NodeType.choices, db_index=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["node_id"]

    def __str__(self) -> str:
        return f"{self.node_id} ({self.ip_address})"


class NetworkRoute(models.Model):
    source_node = models.ForeignKey(
        NetworkNode,
        on_delete=models.CASCADE,
        related_name="outgoing_routes",
    )
    destination_node = models.ForeignKey(
        NetworkNode,
        on_delete=models.CASCADE,
        related_name="incoming_routes",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["source_node__node_id", "destination_node__node_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_node", "destination_node"],
                name="unique_network_route",
            ),
            models.CheckConstraint(
                condition=~models.Q(source_node=models.F("destination_node")),
                name="route_source_not_equal_destination",
            ),
        ]

    def clean(self):
        super().clean()
        source_type = self.source_node.node_type
        destination_type = self.destination_node.node_type
        if source_type == NetworkNode.NodeType.CLIENT and destination_type == NetworkNode.NodeType.CLIENT:
            from django.core.exceptions import ValidationError

            raise ValidationError("client -> client routes are not allowed")

    def __str__(self) -> str:
        return f"{self.source_node.node_id} -> {self.destination_node.node_id}"

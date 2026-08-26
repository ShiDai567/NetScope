"""DRF 序列化器：主要用于 OpenAPI schema 声明（视图手工构建契约响应）。"""

from rest_framework import serializers


class EndpointSchema(serializers.Serializer):
    ip = serializers.CharField()
    port = serializers.IntegerField()
    domain = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    lat = serializers.FloatField(allow_null=True, required=False)
    lng = serializers.FloatField(allow_null=True, required=False)


class NatInfoSchema(serializers.Serializer):
    forward_addr = serializers.CharField(allow_null=True, required=False)
    src_port = serializers.IntegerField(allow_null=True, required=False)
    dst_port = serializers.IntegerField(allow_null=True, required=False)
    original_dst = serializers.CharField(allow_null=True, required=False)


class PacketSchema(serializers.Serializer):
    id = serializers.CharField()
    seq = serializers.IntegerField()
    timestamp = serializers.FloatField()
    born = serializers.FloatField()
    direction = serializers.ChoiceField(choices=["outbound", "inbound", "internal"])
    app_name = serializers.CharField()
    protocol = serializers.CharField()
    status = serializers.CharField(allow_null=True)
    source = EndpointSchema()
    destination = EndpointSchema()
    nat_info = NatInfoSchema(allow_null=True)
    total_up = serializers.IntegerField()
    total_down = serializers.IntegerField()
    interface = serializers.CharField(allow_null=True)
    flag = serializers.CharField(allow_null=True)
    latency_ms = serializers.FloatField(allow_null=True)
    status_since = serializers.FloatField(allow_null=True)


class PacketsResponseSchema(serializers.Serializer):
    server_time = serializers.FloatField()
    last_seq = serializers.IntegerField()
    events = PacketSchema(many=True)


class ModeResponseSchema(serializers.Serializer):
    mode = serializers.CharField()
    uptime = serializers.IntegerField()
    gateway = serializers.DictField()
    ikuai = serializers.DictField()


class DeviceSchema(serializers.Serializer):
    ip = serializers.CharField()
    mac = serializers.CharField(required=False, allow_null=True)
    hostname = serializers.CharField(required=False, allow_null=True)
    vendor = serializers.CharField(required=False, allow_null=True)
    interface = serializers.CharField(required=False, allow_null=True)
    is_gateway = serializers.BooleanField()
    ring_index = serializers.IntegerField(required=False, allow_null=True)
    lat = serializers.FloatField(required=False, allow_null=True)
    lng = serializers.FloatField(required=False, allow_null=True)
    connections = serializers.IntegerField()
    up_rate = serializers.FloatField()
    down_rate = serializers.FloatField()


class NodeSchema(serializers.Serializer):
    ip = serializers.CharField()
    name = serializers.CharField()
    domain = serializers.CharField(allow_null=True)
    lat = serializers.FloatField()
    lng = serializers.FloatField()
    type = serializers.ChoiceField(choices=["gateway", "server", "client"])


class StatsSchema(serializers.Serializer):
    total = serializers.IntegerField()
    active = serializers.IntegerField()
    closed = serializers.IntegerField()
    failed = serializers.IntegerField()
    lost = serializers.IntegerField()
    directions = serializers.DictField()
    protocols = serializers.DictField()
    apps = serializers.ListField()
    bandwidth = serializers.DictField()
    loss_rate = serializers.FloatField()
    avg_latency_ms = serializers.FloatField()
    system = serializers.DictField()
    latency_heatmap = serializers.DictField(required=False)
    mode = serializers.CharField()
    uptime = serializers.IntegerField()
    window = serializers.IntegerField(required=False)

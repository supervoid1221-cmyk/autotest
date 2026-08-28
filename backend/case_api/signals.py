from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ScenarioFlowNode, ScenarioStep


@receiver(post_save, sender=ScenarioStep)
def create_main_flow_node_for_step(sender, instance, created, raw=False, **kwargs):
    """兼容旧入口和录制导入：新接口步骤默认进入主流程末尾。"""
    if raw or not created:
        return
    next_order = (ScenarioFlowNode.objects.filter(
        scenario_id=instance.scenario_id, parent_branch__isnull=True
    ).order_by("-order").values_list("order", flat=True).first() or 0) + 1
    ScenarioFlowNode.objects.get_or_create(
        step=instance,
        defaults={
            "scenario_id": instance.scenario_id,
            "node_type": ScenarioFlowNode.NodeType.ENDPOINT,
            "name": instance.name,
            "order": next_order,
        },
    )

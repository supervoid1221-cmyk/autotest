from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("suite", "0024_suite_visual_schedule")]

    operations = [
        migrations.CreateModel(
            name="WebhookReplayNonce",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nonce_digest", models.CharField(max_length=64, verbose_name="Nonce 摘要")),
                ("request_timestamp", models.BigIntegerField(verbose_name="请求时间戳")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("suite", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="webhook_nonces", to="suite.suite")),
            ],
        ),
        migrations.AddConstraint(
            model_name="webhookreplaynonce",
            constraint=models.UniqueConstraint(fields=("suite", "nonce_digest"), name="unique_suite_webhook_nonce"),
        ),
        migrations.AddIndex(
            model_name="webhookreplaynonce",
            index=models.Index(fields=["created_at"], name="suite_hook_nonce_created_idx"),
        ),
    ]

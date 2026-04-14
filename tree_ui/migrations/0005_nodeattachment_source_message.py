from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tree_ui", "0004_nodeattachment"),
    ]

    operations = [
        migrations.AddField(
            model_name="nodeattachment",
            name="source_message",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="attachments",
                to="tree_ui.nodemessage",
            ),
        ),
    ]

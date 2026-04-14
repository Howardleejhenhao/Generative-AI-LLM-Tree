from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tree_ui", "0005_nodeattachment_source_message"),
    ]

    operations = [
        migrations.AlterField(
            model_name="nodeattachment",
            name="kind",
            field=models.CharField(
                choices=[("image", "Image"), ("pdf", "PDF")],
                default="image",
                max_length=20,
            ),
        ),
    ]

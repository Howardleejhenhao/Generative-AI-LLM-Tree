from django.db import models


class Workspace(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return self.name


class ConversationNode(models.Model):
    class Provider(models.TextChoices):
        OPENAI = "openai", "OpenAI"
        GEMINI = "gemini", "Gemini"

    workspace = models.ForeignKey(
        Workspace,
        related_name="nodes",
        on_delete=models.CASCADE,
    )
    parent = models.ForeignKey(
        "self",
        related_name="children",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )
    edited_from = models.ForeignKey(
        "self",
        related_name="edited_variants",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    title = models.CharField(max_length=160)
    summary = models.CharField(max_length=255, blank=True)
    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        default=Provider.OPENAI,
    )
    model_name = models.CharField(max_length=120)
    position_x = models.IntegerField(default=0)
    position_y = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return self.title


class NodeMessage(models.Model):
    class Role(models.TextChoices):
        SYSTEM = "system", "System"
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    node = models.ForeignKey(
        ConversationNode,
        related_name="messages",
        on_delete=models.CASCADE,
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    order_index = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order_index", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["node", "order_index"],
                name="unique_message_order_per_node",
            )
        ]

    def __str__(self) -> str:
        return f"{self.node_id}:{self.role}:{self.order_index}"

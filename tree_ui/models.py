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
    system_prompt = models.TextField(blank=True)
    temperature = models.FloatField(blank=True, null=True)
    top_p = models.FloatField(blank=True, null=True)
    max_output_tokens = models.PositiveIntegerField(blank=True, null=True)
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


class NodeAttachment(models.Model):
    class Kind(models.TextChoices):
        IMAGE = "image", "Image"

    node = models.ForeignKey(
        ConversationNode,
        related_name="attachments",
        on_delete=models.CASCADE,
    )
    source_message = models.ForeignKey(
        NodeMessage,
        related_name="attachments",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
        default=Kind.IMAGE,
    )
    file = models.FileField(upload_to="node_attachments/%Y/%m/%d")
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.node_id}:{self.kind}:{self.original_name}"


class ConversationMemory(models.Model):
    class Scope(models.TextChoices):
        WORKSPACE = "workspace", "Workspace"
        BRANCH = "branch", "Branch"

    class MemoryType(models.TextChoices):
        FACT = "fact", "Fact"
        PREFERENCE = "preference", "Preference"
        SUMMARY = "summary", "Summary"
        TASK = "task", "Task"
        ARTIFACT = "artifact", "Artifact"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        PINNED = "pinned", "Pinned"
        EXTRACTED = "extracted", "Extracted"

    workspace = models.ForeignKey(
        Workspace,
        related_name="memories",
        on_delete=models.CASCADE,
    )
    scope = models.CharField(
        max_length=20,
        choices=Scope.choices,
        default=Scope.WORKSPACE,
    )
    memory_type = models.CharField(
        max_length=20,
        choices=MemoryType.choices,
        default=MemoryType.FACT,
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.MANUAL,
    )
    branch_anchor = models.ForeignKey(
        ConversationNode,
        related_name="anchored_memories",
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )
    source_node = models.ForeignKey(
        ConversationNode,
        related_name="source_memories",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    source_message = models.ForeignKey(
        NodeMessage,
        related_name="memories",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    title = models.CharField(max_length=160, blank=True)
    content = models.TextField()
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-updated_at", "-created_at"]

    def __str__(self) -> str:
        return f"{self.scope}:{self.memory_type}:{self.title or self.pk}"

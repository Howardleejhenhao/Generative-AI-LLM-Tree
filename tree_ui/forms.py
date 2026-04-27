import json
from django import forms
from tree_ui.models import MCPSource

class MCPSourceForm(forms.ModelForm):
    TRANSPORT_CHOICES = [
        ("stdio", "Stdio (supported)"),
        ("sse", "SSE (supported)"),
        ("stub", "Stub (demo only)"),
    ]

    transport_kind = forms.ChoiceField(
        choices=TRANSPORT_CHOICES,
        required=False,
        label="Transport",
        help_text="Use stdio for the current production-ready MCP path in LLM-Tree.",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    server_label = forms.CharField(
        required=False,
        label="Server label",
        help_text="Human-friendly name shown in diagnostics and tool traces.",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    endpoint = forms.CharField(
        required=False,
        label="Endpoint",
        help_text="Used by remote transports such as SSE. Leave blank for stdio.",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    timeout = forms.FloatField(
        required=False,
        min_value=0.1,
        label="Timeout (seconds)",
        help_text="Applies to MCP transport requests and readiness checks.",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    stdio_command = forms.CharField(
        required=False,
        label="Stdio command",
        help_text="Executable used to start the MCP subprocess, for example `python3`.",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    stdio_args = forms.CharField(
        required=False,
        label="Stdio args",
        help_text="Arguments passed to the stdio command as a JSON array.",
        widget=forms.TextInput(attrs={"class": "form-control font-monospace"}),
    )
    stdio_env_json = forms.CharField(
        required=False,
        label="Stdio env (JSON)",
        help_text="Optional environment overrides for stdio transport as a JSON object.",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control font-monospace"}),
    )
    stdio_cwd = forms.CharField(
        required=False,
        label="Stdio working directory",
        help_text="Optional working directory for the MCP subprocess.",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    enabled_tools_csv = forms.CharField(
        required=False,
        label="Enabled tools",
        help_text="Optional comma-separated allowlist. Leave blank to expose all tools from the source.",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    config_json = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5, 'class': 'form-control font-monospace'}),
        required=False,
        label="Advanced configuration (JSON)",
        help_text="Optional raw JSON merged into the structured fields below for advanced cases."
    )

    class Meta:
        model = MCPSource
        fields = ['name', 'source_id', 'source_type', 'is_enabled', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'source_id': forms.TextInput(attrs={'class': 'form-control'}),
            'source_type': forms.Select(attrs={'class': 'form-select'}),
            'is_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config = self.instance.config if self.instance and self.instance.pk else {}
        transport_kind = config.get("transport_kind", "stdio")
        self.fields["transport_kind"].initial = transport_kind
        self.fields["server_label"].initial = config.get("label", "")
        self.fields["endpoint"].initial = config.get("endpoint", "")
        self.fields["timeout"].initial = config.get("timeout", 30)
        self.fields["stdio_command"].initial = config.get("command", "")
        self.fields["stdio_args"].initial = json.dumps(config.get("args", []))
        self.fields["stdio_env_json"].initial = json.dumps(config.get("env", {}), indent=2)
        self.fields["stdio_cwd"].initial = config.get("cwd", "") or ""
        self.fields["enabled_tools_csv"].initial = ", ".join(config.get("enabled_tools", []))

        advanced_config = config.copy()
        for key in [
            "transport_kind",
            "label",
            "endpoint",
            "timeout",
            "command",
            "args",
            "env",
            "cwd",
            "enabled_tools",
        ]:
            advanced_config.pop(key, None)
        self.fields["config_json"].initial = json.dumps(advanced_config, indent=2) if advanced_config else "{}"

    def clean_config_json(self):
        data = self.cleaned_data['config_json']
        if not data:
            return {}
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid JSON format.")

    def clean_stdio_args(self):
        data = self.cleaned_data.get("stdio_args", "").strip()
        if not data:
            return []
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("Stdio args must be a valid JSON array.") from exc
        if not isinstance(parsed, list):
            raise forms.ValidationError("Stdio args must be a JSON array.")
        return parsed

    def clean_stdio_env_json(self):
        data = self.cleaned_data.get("stdio_env_json", "").strip()
        if not data:
            return {}
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("Stdio env must be a valid JSON object.") from exc
        if not isinstance(parsed, dict):
            raise forms.ValidationError("Stdio env must be a JSON object.")
        return parsed

    def clean_enabled_tools_csv(self):
        data = self.cleaned_data.get("enabled_tools_csv", "")
        if not data.strip():
            return []
        return [item.strip() for item in data.split(",") if item.strip()]

    def clean(self):
        cleaned_data = super().clean()
        source_type = cleaned_data.get("source_type")
        transport_kind = cleaned_data.get("transport_kind") or "stdio"
        stdio_command = (cleaned_data.get("stdio_command") or "").strip()
        endpoint = (cleaned_data.get("endpoint") or "").strip()

        if source_type == MCPSource.SourceType.MCP_SERVER and transport_kind == "stdio" and not stdio_command:
            self.add_error("stdio_command", "Stdio command is required for stdio MCP sources.")
        if source_type == MCPSource.SourceType.MCP_SERVER and transport_kind == "sse" and not endpoint:
            self.add_error("endpoint", "Endpoint is required for SSE MCP sources.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        advanced_config = self.cleaned_data["config_json"].copy()
        source_type = self.cleaned_data["source_type"]

        if source_type == MCPSource.SourceType.MCP_SERVER:
            config = advanced_config
            config["transport_kind"] = self.cleaned_data.get("transport_kind") or "stdio"

            label = (self.cleaned_data.get("server_label") or "").strip()
            if label:
                config["label"] = label

            endpoint = (self.cleaned_data.get("endpoint") or "").strip()
            if endpoint:
                config["endpoint"] = endpoint

            timeout = self.cleaned_data.get("timeout")
            if timeout:
                config["timeout"] = timeout

            enabled_tools = self.cleaned_data.get("enabled_tools_csv", [])
            if enabled_tools:
                config["enabled_tools"] = enabled_tools

            if config["transport_kind"] == "stdio":
                config["command"] = (self.cleaned_data.get("stdio_command") or "").strip()
                config["args"] = self.cleaned_data.get("stdio_args", [])
                env_overrides = self.cleaned_data.get("stdio_env_json", {})
                if env_overrides:
                    config["env"] = env_overrides
                cwd = (self.cleaned_data.get("stdio_cwd") or "").strip()
                if cwd:
                    config["cwd"] = cwd
            instance.config = config
        else:
            instance.config = advanced_config

        if commit:
            instance.save()
        return instance

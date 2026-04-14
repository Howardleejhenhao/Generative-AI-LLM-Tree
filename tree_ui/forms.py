import json
from django import forms
from tree_ui.models import MCPSource

class MCPSourceForm(forms.ModelForm):
    config_json = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5, 'class': 'form-control font-monospace'}),
        required=False,
        label="Configuration (JSON)",
        help_text="Enter source-specific configuration in JSON format."
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
        if self.instance and self.instance.pk:
            self.fields['config_json'].initial = json.dumps(self.instance.config, indent=2)
        else:
            self.fields['config_json'].initial = "{}"

    def clean_config_json(self):
        data = self.cleaned_data['config_json']
        if not data:
            return {}
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid JSON format.")

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.config = self.cleaned_data['config_json']
        if commit:
            instance.save()
        return instance

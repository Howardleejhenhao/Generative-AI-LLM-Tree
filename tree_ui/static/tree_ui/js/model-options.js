export const MODEL_OPTIONS = {
  openai: ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"],
  gemini: ["gemini-2.5-flash", "gemini-2.5-pro"],
};

export function syncModelOptions(providerSelect, modelSelect) {
  const provider = providerSelect.value;
  const options = MODEL_OPTIONS[provider] || [];
  const previousValue = modelSelect.value;
  modelSelect.innerHTML = "";

  for (const option of options) {
    const element = document.createElement("option");
    element.value = option;
    element.textContent = option;
    if (option === previousValue) {
      element.selected = true;
    }
    modelSelect.appendChild(element);
  }
}

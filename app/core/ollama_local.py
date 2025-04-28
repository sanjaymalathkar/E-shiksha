import subprocess
import json

def run_ollama(prompt: str, model: str = "llama3") -> str:
    """
    Run an Ollama model locally using subprocess and return the output as a string.
    Args:
        prompt: The prompt to send to the model.
        model: The Ollama model to use (default: llama3).
    Returns:
        The model's output as a string.
    """
    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            raise RuntimeError(f"Ollama error: {result.stderr}")
        return result.stdout.strip()
    except Exception as e:
        return f"Error running Ollama: {str(e)}"

def run_ollama_json(prompt: str, model: str = "llama3") -> dict:
    """
    Run Ollama and parse the output as JSON.
    """
    output = run_ollama(prompt, model)
    try:
        return json.loads(output)
    except Exception:
        return {"raw": output}

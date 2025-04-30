import subprocess
import json

def run_ollama(prompt, model="llama3"):
    """
    Run an Ollama model locally using subprocess and return the output as a string.
    Args:
        prompt: The prompt to send to the model.
        model: The Ollama model to use (default: llama3).
    Returns:
        The model's output as a string.
    """
    try:
        # Run the Ollama command
        process = subprocess.Popen(
            ["ollama", "run", model, prompt],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Get the output
        stdout, stderr = process.communicate(timeout=60)
        
        if process.returncode != 0:
            print(f"Ollama error: {stderr}")
            return f"Error: {stderr}"
        
        return stdout.strip()
    
    except Exception as e:
        print(f"Error running Ollama: {str(e)}")
        return f"Error: {str(e)}"

def run_ollama_json(prompt, model="llama3"):
    """
    Run Ollama and parse the output as JSON.
    """
    output = run_ollama(prompt, model)
    try:
        return json.loads(output)
    except Exception as e:
        print(f"Error parsing Ollama output as JSON: {str(e)}")
        print(f"Raw output: {output}")
        return {"error": str(e)}

if __name__ == "__main__":
    # Test the model with a simple prompt
    prompt = "Generate a multiple-choice question about computer science."
    print("Running Ollama with prompt:", prompt)
    result = run_ollama(prompt)
    print("\nResult:")
    print(result)
    
    # Test the model with a JSON prompt
    json_prompt = """
    Generate a multiple-choice question about computer science.
    Format the response as a JSON object with these fields:
    - question: the question text
    - options: an array of 4 possible answers
    - answer: the correct answer (one of the options)
    - explanation: why this is the correct answer
    """
    print("\nRunning Ollama with JSON prompt:", json_prompt)
    json_result = run_ollama_json(json_prompt)
    print("\nJSON Result:")
    print(json.dumps(json_result, indent=2))

import os
import logging
import numpy as np
import json
from typing import List, Dict, Any, Optional
from app.core.ollama_local import run_ollama

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default embedding dimensions
EMBEDDING_DIMENSIONS = 384  # A reasonable size for local embeddings

def get_ollama_embedding(text: str, model: str = "llama3") -> List[float]:
    """
    Generate embeddings using Ollama
    
    Args:
        text: The text to embed
        model: The Ollama model to use
        
    Returns:
        List of embedding values
    """
    try:
        # Truncate text if it's too long
        max_text_length = 1000
        if len(text) > max_text_length:
            text = text[:max_text_length]
        
        # Create a prompt that asks for embeddings
        prompt = f"""
        Generate a numerical embedding vector for the following text. 
        The embedding should capture the semantic meaning of the text.
        Return only the embedding vector as a list of {EMBEDDING_DIMENSIONS} floating point numbers.
        
        Text to embed:
        {text}
        """
        
        # Run Ollama to get the embedding
        result = run_ollama(prompt, model=model)
        
        # Parse the result to extract the embedding vector
        # Look for anything that looks like a list of numbers
        import re
        
        # Try to find a JSON array in the response
        matches = re.findall(r'\[[\d\.\-\,\s]+\]', result)
        if matches:
            try:
                # Parse the first match as JSON
                embedding = json.loads(matches[0])
                
                # Ensure it's a list of numbers
                if isinstance(embedding, list) and all(isinstance(x, (int, float)) for x in embedding):
                    # Pad or truncate to match expected dimensions
                    if len(embedding) < EMBEDDING_DIMENSIONS:
                        padding = [0.0] * (EMBEDDING_DIMENSIONS - len(embedding))
                        embedding.extend(padding)
                    elif len(embedding) > EMBEDDING_DIMENSIONS:
                        embedding = embedding[:EMBEDDING_DIMENSIONS]
                    
                    # Normalize the embedding
                    norm = np.linalg.norm(embedding)
                    if norm > 0:
                        embedding = [x / norm for x in embedding]
                    
                    return embedding
            except Exception as e:
                logger.error(f"Error parsing embedding from Ollama response: {e}")
        
        # If we couldn't extract an embedding, generate a random one
        logger.warning("Could not extract embedding from Ollama response, using random embedding")
        return list(np.random.normal(0, 0.1, EMBEDDING_DIMENSIONS))
    
    except Exception as e:
        logger.error(f"Error generating embedding with Ollama: {e}")
        # Return random embedding as fallback
        return list(np.random.normal(0, 0.1, EMBEDDING_DIMENSIONS))

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors
    
    Args:
        vec1: First vector
        vec2: Second vector
        
    Returns:
        Cosine similarity (between -1 and 1)
    """
    # Convert to numpy arrays
    a = np.array(vec1)
    b = np.array(vec2)
    
    # Calculate cosine similarity
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)

def find_similar_chunks(query_embedding: List[float], chunks: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Find chunks similar to the query embedding
    
    Args:
        query_embedding: Query embedding vector
        chunks: List of chunks with embeddings
        top_k: Number of results to return
        
    Returns:
        List of similar chunks with similarity scores
    """
    # Calculate similarity for each chunk
    results = []
    for chunk in chunks:
        try:
            # Get chunk embedding
            chunk_embedding = json.loads(chunk.get("embedding_data", "[]"))
            
            # Calculate similarity
            similarity = cosine_similarity(query_embedding, chunk_embedding)
            
            # Add to results
            results.append({
                "chunk_id": chunk.get("id"),
                "content": chunk.get("content", ""),
                "metadata": json.loads(chunk.get("chunk_metadata", "{}")),
                "similarity": similarity
            })
        except Exception as e:
            logger.error(f"Error calculating similarity for chunk {chunk.get('id')}: {e}")
    
    # Sort by similarity (descending)
    results.sort(key=lambda x: x["similarity"], reverse=True)
    
    # Return top_k results
    return results[:top_k]

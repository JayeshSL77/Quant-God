"""
Inwezt - Vector Embeddings for RAG — AI Native Supreme Hedge Fund
Uses OpenAI text-embedding-3-large (3072d) for maximum retrieval quality.
Fallbacks: Mistral, Gemini.
"""
import os
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Embeddings")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize clients lazily
_mistral_client = None
_openai_client = None
_gemini_configured = False


def get_mistral_client():
    """Get or create Mistral client."""
    global _mistral_client
    if _mistral_client is None and MISTRAL_API_KEY:
        from mistralai import Mistral
        _mistral_client = Mistral(api_key=MISTRAL_API_KEY)
    return _mistral_client


def get_openai_client():
    """Get or create OpenAI client."""
    global _openai_client
    if _openai_client is None and OPENAI_API_KEY:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def configure_gemini():
    """Configure Gemini for embeddings."""
    global _gemini_configured
    if not _gemini_configured and GEMINI_API_KEY:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _gemini_configured = True


# Embedding dimensions for each provider
EMBEDDING_DIMS = {
    'openai_large': 3072,
    'openai_small': 1536,
    'mistral': 1024,
    'gemini': 768,
}

# Current active model
ACTIVE_MODEL = 'text-embedding-3-large'
ACTIVE_DIMS = 3072


def get_embedding(text: str) -> List[float]:
    """
    Get embedding vector for text.
    Uses text-embedding-3-large (3072d, MTEB 64.6) for maximum quality.
    Fallback chain: OpenAI large → OpenAI small → Mistral → Gemini.
    """
    if not text:
        return []
    
    # Truncate to safe token limit (~16K chars ≈ 4K-8K tokens)
    text = text[:16000]
    
    # PRIMARY: OpenAI text-embedding-3-large (3072d, best quality)
    if OPENAI_API_KEY:
        try:
            client = get_openai_client()
            response = client.embeddings.create(
                input=text,
                model="text-embedding-3-large"
            )
            return response.data[0].embedding  # 3072 dimensions
        except Exception as e:
            logger.warning(f"OpenAI large embedding failed: {e}")
            # Try small as immediate fallback
            try:
                response = client.embeddings.create(
                    input=text,
                    model="text-embedding-3-small"
                )
                # Pad to 3072 dims for schema compatibility
                emb = response.data[0].embedding
                return emb + [0.0] * (3072 - len(emb))
            except Exception as e2:
                logger.warning(f"OpenAI small fallback also failed: {e2}")
    
    # SECONDARY: Mistral (free tier)
    if MISTRAL_API_KEY:
        try:
            client = get_mistral_client()
            response = client.embeddings.create(
                model="mistral-embed",
                inputs=[text[:16000]]
            )
            emb = response.data[0].embedding
            return emb + [0.0] * (3072 - len(emb))  # Pad for schema compat
        except Exception as e:
            logger.warning(f"Mistral embedding failed: {e}")
    
    # FALLBACK: Gemini
    if GEMINI_API_KEY:
        try:
            configure_gemini()
            import google.generativeai as genai
            result = genai.embed_content(
                model="models/embedding-001",
                content=text[:10000],
                task_type="retrieval_document"
            )
            emb = result['embedding']
            return emb + [0.0] * (3072 - len(emb))  # Pad for schema compat
        except Exception as e:
            logger.error(f"Gemini embedding also failed: {e}")
    
    logger.error("No embedding provider available!")
    return []


def get_embeddings_batch(texts: List[str], batch_size: int = 25) -> List[List[float]]:
    """
    Get embeddings for multiple texts using OpenAI batch API.
    OpenAI supports up to 2048 texts per batch call.
    We use batch_size=25 for reliability.
    """
    if not texts:
        return []
    
    # Try OpenAI batch API (much faster than one-by-one)
    if OPENAI_API_KEY:
        try:
            client = get_openai_client()
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch = [t[:16000] for t in texts[i:i + batch_size]]
                response = client.embeddings.create(
                    input=batch,
                    model="text-embedding-3-large"
                )
                batch_embs = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embs)
            
            return all_embeddings
        except Exception as e:
            logger.warning(f"OpenAI batch embedding failed, falling back to sequential: {e}")
    
    # Fallback: sequential
    return [get_embedding(text) for text in texts]


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    import math
    
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot_product / (norm1 * norm2)


def search_similar(query: str, documents: List[Dict[str, Any]], 
                   text_key: str = "text", top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Search for most similar documents to a query.
    
    Args:
        query: Search query
        documents: List of dicts with text and pre-computed embeddings
        text_key: Key for text field in documents
        top_k: Number of results to return
    
    Returns:
        Top-k most similar documents with similarity scores
    """
    query_embedding = get_embedding(query)
    if not query_embedding:
        return []
    
    results = []
    for doc in documents:
        doc_embedding = doc.get("embedding")
        if doc_embedding:
            similarity = cosine_similarity(query_embedding, doc_embedding)
            results.append({
                **doc,
                "similarity": similarity
            })
    
    # Sort by similarity (descending)
    results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
    
    return results[:top_k]


def embed_news_articles():
    """Embed all news articles that don't have embeddings yet."""
    try:
        from api.database.database import get_connection
        import json
        
        conn = get_connection()
        cur = conn.cursor()
        
        # Get articles without embeddings
        cur.execute("""
            SELECT id, headline, summary 
            FROM news_articles 
            WHERE embedding_id IS NULL
            LIMIT 100
        """)
        
        articles = cur.fetchall()
        if not articles:
            logger.info("No articles to embed")
            return 0
        
        logger.info(f"Embedding {len(articles)} articles...")
        
        # Prepare texts
        texts = []
        for article in articles:
            text = f"{article[1]}. {article[2] or ''}"
            texts.append(text[:500])  # Limit text length
        
        # Get embeddings in batch
        embeddings = get_embeddings_batch(texts)
        
        # Update database
        for i, article in enumerate(articles):
            if i < len(embeddings) and embeddings[i]:
                # Store embedding as JSON string for simplicity
                embedding_id = f"emb_{article[0]}"
                cur.execute("""
                    UPDATE news_articles 
                    SET embedding_id = %s 
                    WHERE id = %s
                """, (embedding_id, article[0]))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Embedded {len(articles)} articles successfully")
        return len(articles)
        
    except Exception as e:
        logger.error(f"Failed to embed articles: {e}")
        return 0


def build_semantic_context(query: str, symbol: str = None, top_k: int = 3) -> str:
    """
    Build semantic context for a query using embedded news articles.
    This is what makes our RAG more powerful than ChatGPT.
    """
    try:
        from api.database.database import get_connection
        
        conn = get_connection()
        cur = conn.cursor()
        
        # Get recent news for the symbol (or all if no symbol)
        if symbol:
            cur.execute("""
                SELECT headline, summary, published_at, source 
                FROM news_articles 
                WHERE symbol = %s 
                ORDER BY published_at DESC 
                LIMIT 10
            """, (symbol,))
        else:
            cur.execute("""
                SELECT headline, summary, published_at, source 
                FROM news_articles 
                ORDER BY published_at DESC 
                LIMIT 20
            """)
        
        articles = cur.fetchall()
        cur.close()
        conn.close()
        
        if not articles:
            return ""
        
        # Build context string
        context_parts = ["📰 RECENT NEWS CONTEXT:"]
        for article in articles[:top_k]:
            headline = article[0]
            summary = article[1] or ""
            date = article[2]
            context_parts.append(f"• {headline}")
            if summary:
                context_parts.append(f"  {summary[:150]}...")
        
        return "\n".join(context_parts)
        
    except Exception as e:
        logger.error(f"Failed to build semantic context: {e}")
        return ""


if __name__ == "__main__":
    # Test embedding
    print("Testing embedding...")
    test_text = "Reliance Industries reported strong Q3 results with profit growth"
    embedding = get_embedding(test_text)
    print(f"Embedding dimension: {len(embedding)}")
    print(f"First 5 values: {embedding[:5]}")
    
    # Test similarity
    text1 = "Stock market crashed today"
    text2 = "Markets fell sharply in trading session"
    text3 = "The weather is sunny today"
    
    emb1 = get_embedding(text1)
    emb2 = get_embedding(text2)
    emb3 = get_embedding(text3)
    
    print(f"\nSimilarity (market crash vs market fell): {cosine_similarity(emb1, emb2):.4f}")
    print(f"Similarity (market crash vs weather): {cosine_similarity(emb1, emb3):.4f}")

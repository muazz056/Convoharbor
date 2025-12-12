from flask import current_app
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Import for demo mode fallback
try:
    from sentence_transformers import SentenceTransformer
    DEMO_MODE_AVAILABLE = True
except ImportError:
    DEMO_MODE_AVAILABLE = False

def generate_embeddings_for_texts(texts: list[str]) -> dict:
    """
    Generates embeddings for a list of texts using both OpenAI and Gemini.
    🚀 DEMO MODE: Falls back to local embeddings when API keys are invalid.

    Args:
        texts: A list of string chunks to be embedded.

    Returns:
        A dictionary containing the generated embeddings and any errors.
        Example:
        {
            "openai_embeddings": [[0.1, ...], [0.2, ...]],
            "gemini_embeddings": [[0.3, ...], [0.4, ...]],
            "errors": {
                "openai": "API key not found."
            }
        }
    """
    # Debug input validation
    # current_app.logger.info(f"🔍 [EMBED] Input texts type: {type(texts)}")
    # current_app.logger.info(f"🔍 [EMBED] Input texts is None: {texts is None}")
    if texts is not None:
        try:
            # current_app.logger.info(f"🔍 [EMBED] Input texts length: {len(texts)}")
            pass
        except Exception as e:
            current_app.logger.error(f"❌ [EMBED] Error getting texts length: {e}")
            current_app.logger.error(f"❌ [EMBED] texts value: {repr(texts)}")
            raise e
    results = {
        "openai_embeddings": None,
        "gemini_embeddings": None,
        "errors": {}
    }

    # --- Generate OpenAI Embeddings ---
    openai_api_key = current_app.config['OPENAI_API_KEY']
    if openai_api_key and not openai_api_key.startswith('your-'):
        try:
            current_app.logger.info(f"🔑 Attempting OpenAI embeddings for {len(texts)} texts")
            openai_embedder = OpenAIEmbeddings(
                model="text-embedding-3-large",
                api_key=openai_api_key
            )
            results["openai_embeddings"] = openai_embedder.embed_documents(texts)
            current_app.logger.info(f"✅ OpenAI embeddings generated successfully: {len(results['openai_embeddings'])} vectors")
        except Exception as e:
            current_app.logger.error(f"❌ OpenAI embeddings failed: {str(e)}")
            results["errors"]["openai"] = f"Failed to generate OpenAI embeddings: {str(e)}"
    else:
        current_app.logger.warning("⚠️ OpenAI API key not configured")
        results["errors"]["openai"] = "OpenAI API key not provided or is placeholder."

    # --- Generate Gemini Embeddings ---
    gemini_api_key = current_app.config['GEMINI_API_KEY']
    if gemini_api_key and not gemini_api_key.startswith('your-'):
        try:
            gemini_embedder = GoogleGenerativeAIEmbeddings(
                model=current_app.config['GEMINI_EMBEDDING_MODEL'],
                google_api_key=gemini_api_key
            )
            results["gemini_embeddings"] = gemini_embedder.embed_documents(texts)
        except Exception as e:
            results["errors"]["gemini"] = f"Failed to generate Gemini embeddings: {str(e)}"
    else:
        results["errors"]["gemini"] = "Gemini API key not provided or is placeholder."

    # 🚀 DEMO MODE: Use local embeddings if both providers failed
    if results["openai_embeddings"] is None and results["gemini_embeddings"] is None:
        if DEMO_MODE_AVAILABLE:
            try:
                current_app.logger.info("🎯 DEMO MODE: Using local sentence-transformers for embeddings")
                
                # Add timeout and better error handling for model loading
                import socket
                original_timeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(5)  # Reduced to 5 seconds to fail faster
                
                try:
                    local_model = SentenceTransformer('all-MiniLM-L6-v2')
                    local_embeddings = local_model.encode(texts).tolist()
                except Exception as model_error:
                    socket.setdefaulttimeout(original_timeout)
                    current_app.logger.error(f"❌ Local model loading failed: {model_error}")
                    raise ValueError("Local embedding model unavailable due to network issues. Please configure OpenAI or Gemini API keys.")
                finally:
                    socket.setdefaulttimeout(original_timeout)  # Restore original timeout
                
                # Validate local embeddings
                if not local_embeddings:
                    raise ValueError("Local embedding generation returned empty results")
                
                # Use local embeddings for both providers in demo mode
                results["openai_embeddings"] = local_embeddings
                results["gemini_embeddings"] = local_embeddings
                
                # Clear errors since we have a working fallback
                results["errors"] = {
                    "demo_mode": "Using local embeddings - add real API keys for full functionality"
                }
                
                current_app.logger.info(f"✅ DEMO MODE: Generated {len(local_embeddings)} local embeddings")
                
            except Exception as e:
                current_app.logger.error(f"❌ DEMO MODE failed: {e}")
                if "timeout" in str(e).lower() or "connection" in str(e).lower():
                    results["errors"]["demo_fallback"] = f"Network timeout loading embedding model. Check internet connection or use API keys for cloud embeddings."
                else:
                    results["errors"]["demo_fallback"] = f"Local embedding generation failed: {str(e)}"
        else:
            results["errors"]["demo_unavailable"] = "Demo mode not available - install sentence-transformers for local fallback"

    return results
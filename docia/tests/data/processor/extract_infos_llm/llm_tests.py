import sys
import time
from unittest import mock
import pytest

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from openai import RateLimitError

sys.path.append('.')

from app.processor.analyze_content import LLMEnvironment
from app.ai_models.config_albert import API_KEY_ALBERT, BASE_URL_PROD

# Patcher la fonction


def test_rate_limiting(num_calls: int = 120, max_workers: int = 60):
    """
    Script pour tester le rate limiting de l'API LLM en effectuant 
    plus de 100 appels par minute.
    """
    # Initialisation de l'environnement LLM
    llm_env = LLMEnvironment(
        api_key=API_KEY_ALBERT,
        base_url=BASE_URL_PROD,
        llm_model="albert-large"
    )
    
    
    print(f"Début du test de rate limiting à {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Nombre d'appels prévus: {num_calls}")
    print(f"Nombre de threads parallèles: {max_workers}")
    print("-" * 60)
    
    start_time = time.time()
    results = []
    errors = []
    
    def make_api_call(call_id):
        """Fonction pour effectuer un appel API avec un message unique pour éviter le cache"""
        try:
            # Créer un message unique pour chaque appel en ajoutant un identifiant et le contexte
            # Cela évite que l'API utilise le cache et augmente la taille de la requête
            unique_message = [
                {"role": "system", "content": "Vous êtes un assistant utile qui analyse des histoires."},
                {"role": "user", "content": f"Question: Répondez simplement 'OK' à ce message ainsi que l'identifiant de la requête ci-après. Identifiant de requête: {call_id}. N'hésitez pas à rajouter un message aléatoire inspiré du numéro de la requête."}
            ]
            response = llm_env.ask_llm(message=unique_message, temperature=0.0)
            return {
                "call_id": call_id,
                "status": "success",
                "response": response[:50] if response else "None",
                "error": None
            }
        except Exception as e:
            return {
                "call_id": call_id,
                "status": "error",
                "response": None,
                "error_msg": str(e),
                "error":e
            }
    
    # Exécution des appels en parallèle
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Soumettre tous les appels
        futures = {executor.submit(make_api_call, i): i for i in range(num_calls)}
        
        # Collecter les résultats au fur et à mesure
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            
            if result["status"] == "error":
                errors.append(result)
                print(f"❌ Appel {result['call_id']} échoué: {result['error_msg'][:200]}")
            else:
                print(f"✅ Appel {result['call_id']} réussi")
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # Statistiques
    successful_calls = sum(1 for r in results if r["status"] == "success")
    failed_calls = len(errors)
    calls_per_minute = (num_calls / elapsed_time) * 60 if elapsed_time > 0 else 0
    
    print("-" * 60)
    print(f"Test terminé à {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Temps écoulé: {elapsed_time:.2f} secondes")
    print(f"Appels réussis: {successful_calls}/{num_calls}")
    print(f"Appels échoués: {failed_calls}/{num_calls}")
    print(f"Taux d'appels: {calls_per_minute:.2f} appels/minute")
    
    # Afficher les erreurs de rate limiting
    rate_limit_errors = [e for e in errors if "rate limit" in e["error_msg"].lower() or 
                         "429" in e["error_msg"] or "too many" in e["error_msg"].lower()]
    
    if rate_limit_errors:
        print("\n" + "=" * 60)
        print("🚨 ERREURS DE RATE LIMITING DÉTECTÉES:")
        print("=" * 60)
        for error in rate_limit_errors[:5]:  # Afficher les 5 premières
            print(f"\nAppel {error['call_id']}:")
            print(f"  {error['error_msg']}")
    else:
        print("\n⚠️  Aucune erreur de rate limiting détectée.")
        print("   Les erreurs rencontrées:")
        for error in errors[:5]:  # Afficher les 5 premières erreurs
            print(f"  - Appel {error['call_id']}: {error['error_msg'][:100]}")
    
    return results


def test_ask_llm_rate_limit_error():
    """
    Test que ask_llm gère correctement les erreurs de rate limiting (429).
    """
    message = [
        {"role": "system", "content": "Vous êtes un assistant utile qui analyse des histoires."},
        {"role": "user", "content": "Question: Répondez simplement 'OK' à ce message."}
    ]
    
    # Créer l'objet d'abord
    llm_env = LLMEnvironment(
        api_key=API_KEY_ALBERT,
        base_url=BASE_URL_PROD,
        llm_model="albert-large"
    )
    
    # Mocker la méthode create de l'instance
    with mock.patch.object(llm_env.client.chat.completions, "create") as mock_create:
        # Configurer le mock pour lever une RateLimitError
        # RateLimitError peut être créé simplement avec un message
        error_message = "Error code: 429 - {'detail': '100 requests for albert-large per minute exceeded (remaining: 0).'}"
        mock_create.side_effect = RateLimitError(error_message)
        
        # Appeler ask_llm - cela devrait lever une exception après les retries
        with pytest.raises(Exception) as exc_info:
            llm_env.ask_llm(message=message, temperature=0.0, max_retries=1)
        
        # Vérifier que create a été appelé
        assert mock_create.call_count == 1
        
        # Vérifier les arguments passés (en kwargs, pas en args positionnels)
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["model"] == "albert-large"
        assert call_kwargs["messages"] == message
        assert call_kwargs["temperature"] == 0.0
        # response_format est toujours passé (peut être None)
        assert call_kwargs.get("response_format") is None
        
        # Vérifier que l'erreur contient bien 429
        assert "429" in str(exc_info.value) or "rate limiting" in str(exc_info.value).lower()
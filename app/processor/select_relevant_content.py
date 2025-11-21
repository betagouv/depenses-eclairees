"""
Soit pas besoin et on passe tout le texte en entrée. 
Soit on veux faire de l'embedding pour sélectionner seulement les parties pertinentes.

Prend en entrée du texte et 
"""

import pandas as pd
import numpy as np
from openai import OpenAI
import json
import faiss
import time
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import csr_matrix
import scipy.sparse
from tqdm import tqdm
from typing import List, Dict, Tuple, Optional, Union, Any
from concurrent.futures import ThreadPoolExecutor

from app.data.sql.sql import bulk_update_attachments
from app.utils import getDate
from app.processor.attributes_query import select_attr

from app.grist import update_records_in_grist
from app.grist import API_KEY_GRIST, URL_TABLE_ATTACHMENTS


class RAGEnvironment:
    """
    Environnement RAG optimisé avec FAISS pour l'indexation et la recherche rapide.
    Supporte la recherche hybride (sémantique + lexicale).
    """
# init
    def __init__(
        self, 
        api_key: str,
        base_url: Optional[str] = None,
        embedding_model: str = "BAAI/bge-m3",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        embedding_dimension: int = 1024,  # Dimension par défaut pour BGE-M3
        hybrid_search: bool = True,
        semantic_weight: float = 0.7,  # Poids de la recherche sémantique (1-semantic_weight = poids lexical)
        retrieval_top_k: int = 3,  # Nombre de chunks à récupérer par défaut
        max_car: int = 10000,  # Nombre de charactères maximum dans un contexte
    ):
        """
        Initialise l'environnement RAG.
        
        Args:
            api_key: Clé API OpenAI
            base_url: URL de base pour l'API OpenAI (facultatif)
            embedding_model: Modèle d'embedding à utiliser
            chunk_size: Taille des chunks en caractères
            chunk_overlap: Chevauchement entre les chunks en caractères
            embedding_dimension: Dimension des vecteurs d'embedding
            hybrid_search: Activer la recherche hybride (sémantique + lexicale)
            semantic_weight: Poids de la recherche sémantique (0 à 1)
            retrieval_top_k: Nombre de chunks à récupérer lors de la recherche
        """
        self.api_key = api_key
        self.base_url = base_url
        self.embedding_model = embedding_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_dimension = embedding_dimension
        self.hybrid_search = hybrid_search
        self.semantic_weight = max(0.0, min(1.0, semantic_weight))  # Limiter entre 0 et 1
        self.retrieval_top_k = max(1, retrieval_top_k)  # Au moins 1 chunk
        self.max_car = max_car
        
        # Initialisation du client OpenAI
        self.client = self._initialize_openai_client()
        
        # Dictionnaire pour stocker les documents traités
        self.documents = {}
        
        # Initialisation de FAISS (sera créé lors de l'indexation)
        self.index = None
        self.chunks = []
        
        # Initialisation de l'index lexical (TF-IDF)
        self.tfidf_vectorizer = TfidfVectorizer(
            lowercase=True, 
            stop_words='english',
            ngram_range=(1, 2),
            max_df=0.85,
            min_df=2
        )
        self.tfidf_matrix = None

# API LLM à remplacer par un appel à une fonction dédiée
    def _initialize_openai_client(self) -> OpenAI:
        """
        Initialise le client OpenAI avec la clé API fournie et éventuellement une URL de base personnalisée.
        
        Returns:
            Instance du client OpenAI
        """
        client_kwargs = {"api_key": self.api_key}
        
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
            
        return OpenAI(**client_kwargs)

# chunks 

    def _split_text_into_chunks(self,
        text: str,
        doc_id: str = ""
    ) -> List[Dict[str, str]]:
        """
        Divise un texte en morceaux (chunks) de taille fixe avec un chevauchement optionnel.
        
        Args:
            text (str): Le texte à découper.
            chunk_size (int): La taille de chaque chunk.
            chunk_overlap (int): Le nombre de caractères de chevauchement entre les chunks.
            doc_id (str): Identifiant du document (facultatif).
            
        Returns:
            List[Dict[str, str]]: Liste de chunks avec métadonnées.
        """
        # Nettoyage du texte
        if not isinstance(text, str):
            try:
                text = str(text)
            except Exception:
                return []
        
        text = text.replace('\x00', '').strip()

        if not text:
            return []

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("Le chevauchement doit être strictement inférieur à la taille du chunk.")
        
        chunks = []
        start = 0
        chunk_id = 0
        text_length = len(text)

        while start < text_length:
            end = min(start + self.chunk_size, text_length)
            chunk_text = text[start:end]

            chunks.append({
                "text": chunk_text,
                "doc_id": doc_id,
                "chunk_id": f"{doc_id}_{chunk_id}" if doc_id else str(chunk_id),
                "start_char": start,
                "end_char": end
            })

            # Calcul du prochain start
            start += self.chunk_size - self.chunk_overlap
            chunk_id += 1

        return chunks
    
# embedding

    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Génère des embeddings pour une liste de textes en utilisant l'API OpenAI.
        Version robuste avec meilleure gestion des erreurs et des textes problématiques.
        
        Args:
            texts: Liste de textes à encoder
            
        Returns:
            Matrice d'embeddings où chaque ligne est un embedding
        """
        if not texts:
            return np.array([], dtype=np.float32)
        
        # Nettoyer et valider les textes avant l'embedding
        cleaned_texts = []
        for i, text in enumerate(texts):
            if not isinstance(text, str):
                try:
                    text = str(text)
                except Exception:
                    # logger.warning(f"Texte {i} non convertible en string. Utilisation d'une chaîne vide.")
                    text = ""
            
            # Nettoyer le texte
            # Supprimer les caractères nuls et autres contrôles qui peuvent causer des problèmes
            text = text.replace('\x00', ' ').replace('\r', ' ').replace('\t', ' ')
            
            # Nettoyer les espaces multiples
            while '  ' in text:
                text = text.replace('  ', ' ')
            
            # Si texte trop long, tronquer pour éviter les problèmes avec l'API
            max_text_length = 8000  # Limite raisonnable pour un seul texte
            if len(text) > max_text_length:
                text = text[:max_text_length]
                # logger.warning(f"Texte {i} tronqué à {max_text_length} caractères pour l'embedding")
            
            cleaned_texts.append(text)
        
        # Traitement par lots pour éviter des requêtes trop volumineuses
        batch_size = 16  # Réduire la taille du batch pour plus de robustesse
        all_embeddings = []
        
        for i in range(0, len(cleaned_texts), batch_size):
            batch = cleaned_texts[i:i + batch_size]
            
            # Tentatives multiples en cas d'erreur
            max_retries = 3
            for retry in range(max_retries):
                try:
                    # Mesurer le temps de traitement
                    start_time = time.time()
                    
                    # Appel à l'API avec timeout
                    response = self.client.embeddings.create(
                        model=self.embedding_model,
                        input=batch,
                        encoding_format="float"
                    )
                    
                    # Extraire les vecteurs d'embedding
                    batch_embeddings = [item.embedding for item in response.data]
                    
                    # Vérifier que le nombre d'embeddings correspond au nombre de textes
                    if len(batch_embeddings) != len(batch):
                        # logger.warning(f"Nombre d'embeddings reçus ({len(batch_embeddings)}) différent du nombre de textes envoyés ({len(batch)})")
                        # Compléter avec des vecteurs nuls si nécessaire
                        if len(batch_embeddings) < len(batch):
                            for _ in range(len(batch) - len(batch_embeddings)):
                                batch_embeddings.append([0.0] * self.embedding_dimension)
                        else:
                            # Tronquer si trop d'embeddings (cas improbable)
                            batch_embeddings = batch_embeddings[:len(batch)]
                    
                    all_embeddings.extend(batch_embeddings)
                    
                    if i == 0 or retry > 0:  # Log pour le premier batch ou en cas de retry réussi
                        continue
                        # logger.info(f"Embedding batch {i//batch_size + 1} processed in {time.time() - start_time:.2f}s (retry {retry})")
                    
                    # Sortir de la boucle de retry en cas de succès
                    break
                    
                except Exception as e:
                    # logger.error(f"ERREUR lors de la génération d'embeddings (batch {i//batch_size + 1}, retry {retry}): {str(e)}")
                    
                    if retry < max_retries - 1:
                        # Attendre avant de réessayer (backoff exponentiel)
                        wait_time = 2 ** retry
                        # logger.info(f"Nouvelle tentative dans {wait_time} secondes...")
                        time.sleep(wait_time)
                    else:
                        # Dernier essai échoué, ajouter des vecteurs nuls
                        # logger.warning(f"Échec après {max_retries} tentatives. Utilisation de vecteurs nuls.")
                        for _ in range(len(batch)):
                            all_embeddings.append([0.0] * self.embedding_dimension)
        
        # Vérification finale
        if len(all_embeddings) != len(texts):
            # logger.error(f"Nombre final d'embeddings ({len(all_embeddings)}) différent du nombre de textes ({len(texts)})")
            # Ajuster la taille si nécessaire
            if len(all_embeddings) < len(texts):
                for _ in range(len(texts) - len(all_embeddings)):
                    all_embeddings.append([0.0] * self.embedding_dimension)
            else:
                all_embeddings = all_embeddings[:len(texts)]
        
        # Convertir en numpy array
        try:
            embeddings_array = np.array(all_embeddings, dtype=np.float32)
            
            # Vérifier la forme de l'array
            if embeddings_array.shape[1] != self.embedding_dimension:
                # logger.warning(f"Dimension des embeddings ({embeddings_array.shape[1]}) différente de la dimension attendue ({self.embedding_dimension})")
                # Réinitialiser avec des vecteurs de la bonne taille
                embeddings_array = np.zeros((len(texts), self.embedding_dimension), dtype=np.float32)
            
            return embeddings_array
            
        except Exception as e:
            # logger.error(f"Erreur lors de la conversion en numpy array: {str(e)}")
            # Fallback: retourner des vecteurs nuls
            return np.zeros((len(texts), self.embedding_dimension), dtype=np.float32)

    def add_documents(self, texts: Union[List[str], Dict[str, str]], doc_ids: Optional[List[str]] = None) -> None:
        """
        Ajoute des documents à l'environnement RAG.
        
        Args:
            texts: Liste de textes ou dictionnaire {id: texte}
            doc_ids: Liste d'identifiants de documents (facultatif, utilisé si texts est une liste)
        
        Returns: (ajout AMA)
            chunks
            index
            tfidf_matrix
            tfidf_vectorizer

        """
        try:
            # Conversion en dictionnaire si texts est une liste
            if isinstance(texts, list):
                if doc_ids is None:
                    doc_ids = [str(i) for i in range(len(texts))]
                if len(doc_ids) != len(texts):
                    # logger.warning(f"Nombre d'identifiants ({len(doc_ids)}) différent du nombre de textes ({len(texts)}). Utilisation des {min(len(doc_ids), len(texts))} premiers.")
                    min_len = min(len(doc_ids), len(texts))
                    doc_ids = doc_ids[:min_len]
                    texts = texts[:min_len]
                texts_dict = dict(zip(doc_ids, texts))
            else:
                texts_dict = texts
            
            # Mise à jour du dictionnaire de documents
            self.documents.update(texts_dict)
            
            # Prétraitement des documents
            # logger.info("Découpage des documents en chunks...")
            new_chunks = []
            
            # Traitement document par document avec gestion des erreurs
            for doc_id, text in texts_dict.items():
                try:
                    if not text:
                        # logger.warning(f"Document {doc_id} contient un texte vide. Ignoré.")
                        continue
                    
                    if not isinstance(text, str):
                        try:
                            text = str(text)
                            # logger.warning(f"Document {doc_id}: conversion forcée en string")
                        except Exception as e:
                            # logger.warning(f"Document {doc_id} non convertible en string: {str(e)}. Ignoré.")
                            continue
                    
                    # Nettoyage de base du texte
                    text = text.replace('\x00', '')
                    
                    # Vérifier à nouveau après nettoyage
                    if not text:
                        # logger.warning(f"Document {doc_id} vide après nettoyage. Ignoré.")
                        continue
                    
                    # Limiter la taille du texte pour éviter les problèmes de mémoire
                    max_text_length = 1000000  # environ 1000 pages
                    if len(text) > max_text_length:
                        # logger.warning(f"Texte tronqué de {len(text)} à {max_text_length} caractères pour le document {doc_id}")
                        text = text[:max_text_length]
                    
                    # Création des chunks avec gestion d'erreur
                    try:
                        doc_chunks = self._split_text_into_chunks(text, doc_id)
                        if doc_chunks:
                            new_chunks.extend(doc_chunks)
                            # logger.info(f"Document {doc_id} découpé en {len(doc_chunks)} chunks")
                        else:
                            continue
                            # logger.warning(f"Aucun chunk créé pour le document {doc_id}")
                    except Exception as e:
                        # logger.error(f"Erreur lors du découpage du document {doc_id}: {str(e)}")
                        # Fallback: créer un seul chunk avec le début du document
                        try:
                            fallback_chunk = {
                                "text": text[:min(len(text), 5000)],
                                "doc_id": doc_id,
                                "chunk_id": f"{doc_id}_0",
                                "start_char": 0,
                                "end_char": min(len(text), 5000)
                            }
                            new_chunks.append(fallback_chunk)
                            # logger.info(f"Fallback: Document {doc_id} ajouté comme un seul chunk")
                        except Exception as e2:
                            print(e2)
                            # logger.error(f"Échec du fallback pour {doc_id}: {str(e2)}")
                
                except Exception as e:
                    print(e)
                    # logger.error(f"Erreur complète lors du traitement du document {doc_id}: {str(e)}")
            
            # Vérifier qu'il y a des chunks à traiter
            if not new_chunks:
                # logger.warning("Aucun chunk valide n'a été créé. Rien à indexer.")
                return
            
            # Construction de l'index TF-IDF pour la recherche hybride si activée
            if self.hybrid_search:
                self._update_tfidf_index(new_chunks)
            
            # Génération des embeddings par lots pour éviter les erreurs de mémoire
            total_chunks = len(new_chunks)
            # logger.info(f"Génération des embeddings pour {total_chunks} chunks...")
            
            # Taille du lot pour le traitement d'embedding
            batch_size = 500  # Plus petit batch pour éviter les problèmes de mémoire
            all_embeddings = []
            
            for i in range(0, total_chunks, batch_size):
                end_idx = min(i + batch_size, total_chunks)
                batch_chunks = new_chunks[i:end_idx]
                
                # logger.info(f"Traitement du lot d'embeddings {i//batch_size + 1}/{(total_chunks-1)//batch_size + 1} ({len(batch_chunks)} chunks)")
                
                try:
                    # Extraire les textes des chunks
                    text_chunks = [chunk["text"] for chunk in batch_chunks]
                    
                    # Générer les embeddings pour ce lot
                    batch_embeddings = self._get_embeddings(text_chunks)
                    
                    # Vérifier que les embeddings ont été générés
                    if len(batch_embeddings) == 0:
                        # logger.warning(f"Aucun embedding généré pour le lot {i//batch_size + 1}")
                        # Génération de vecteurs nuls comme fallback
                        batch_embeddings = np.zeros((len(batch_chunks), self.embedding_dimension), dtype=np.float32)
                    
                    # Ajouter à l'index FAISS
                    if self.index is None:
                        # Premier lot: créer l'index
                        self._create_index(batch_embeddings)
                        self.chunks = batch_chunks
                    else:
                        # Lots suivants: mettre à jour l'index
                        self.index.add(batch_embeddings)
                        self.chunks.extend(batch_chunks)
                    
                    # logger.info(f"Lot {i//batch_size + 1} indexé avec succès")
                    
                except Exception as e:
                    print(e)
                    # logger.error(f"Erreur lors du traitement du lot d'embeddings {i//batch_size + 1}: {str(e)}")
            
            # logger.info(f"Index FAISS mis à jour avec succès. Nombre total de chunks: {len(self.chunks)}")
                        
        except Exception as e:
            print(e)
            # logger.error(f"Erreur critique dans add_documents: {str(e)}")
            # logger.error("Les documents n'ont pas été correctement indexés")

    
    def _create_index(self, embeddings: np.ndarray) -> None:
        """
        Crée un index FAISS à partir d'embeddings.
        
        Args:
            embeddings: Matrice d'embeddings où chaque ligne est un embedding
        """
        try:
            # Créer un index L2 (distance euclidienne)
            self.index = faiss.IndexFlatL2(self.embedding_dimension)
            
            # Ajouter les embeddings à l'index
            self.index.add(embeddings)
            
            # logger.info(f"Index FAISS créé avec {self.index.ntotal} vecteurs")
            
        except Exception as e:
            # logger.error(f"Erreur lors de la création de l'index FAISS: {str(e)}")
            # Fallback: créer un index vide
            self.index = faiss.IndexFlatL2(self.embedding_dimension)
    
    def _update_tfidf_index(self, new_chunks: List[Dict[str, str]]) -> None:
        """
        Met à jour l'index TF-IDF avec de nouveaux chunks.
        
        Args:
            new_chunks: Nouveaux chunks à ajouter
        """
        try:
            # Extraire les textes des chunks
            chunk_texts = [chunk["text"] for chunk in new_chunks]
            
            if not self.tfidf_matrix:
                # Premier ajout: créer l'index TF-IDF
                # logger.info("Création de l'index TF-IDF...")
                self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(chunk_texts)
                # logger.info(f"Index TF-IDF créé avec {self.tfidf_matrix.shape[0]} chunks et {self.tfidf_matrix.shape[1]} termes")
            else:
                # Mise à jour de l'index existant
                # logger.info("Mise à jour de l'index TF-IDF...")
                
                # Si nous avons de nouveaux termes, nous devons reconstruire l'index complet
                old_chunk_texts = [chunk["text"] for chunk in self.chunks]
                all_texts = old_chunk_texts + chunk_texts
                
                # Reconstruire la matrice TF-IDF avec tous les textes
                self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(all_texts)
                # logger.info(f"Index TF-IDF mis à jour avec {self.tfidf_matrix.shape[0]} chunks et {self.tfidf_matrix.shape[1]} termes")
        
        except Exception as e:
            # logger.error(f"Erreur lors de la mise à jour de l'index TF-IDF: {str(e)}")
            # Fallback: désactiver la recherche hybride en cas d'erreur
            # logger.warning("Recherche hybride temporairement désactivée en raison d'une erreur d'indexation")
            self.hybrid_search = False

# recherche dans l'embedding

    def _search_semantic(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Tuple[int, float]]:
        """
        Recherche sémantique avec FAISS.
        
        Args:
            query_embedding: Embedding de la requête
            top_k: Nombre de résultats à retourner
            
        Returns:
            Liste de tuples (indice, score) pour les chunks les plus pertinents
        """
        if self.index is None:
            return []
        
        # Recherche des K plus proches voisins
        distances, indices = self.index.search(query_embedding, top_k)
        
        # Normaliser les distances (convertir en scores de similarité entre 0 et 1)
        # Les distances FAISS sont des distances L2 (plus elles sont petites, meilleures elles sont)
        # Trouver la distance maximale pour normaliser
        max_dist = np.max(distances[0]) if distances.size > 0 else 1.0
        if max_dist == 0:
            max_dist = 1.0  # Éviter la division par zéro
        
        # Convertir les distances en scores (1 - distance normalisée)
        scores = [1.0 - (dist / max_dist) for dist in distances[0]]
        
        # Retourner les paires (indice, score)
        return [(int(idx), float(score)) for idx, score in zip(indices[0], scores)]

    def _search_lexical(self, query: str, top_k: int = 5) -> List[Tuple[int, float]]:
        """
        Recherche lexicale avec TF-IDF.
        
        Args:
            query: Requête de recherche
            top_k: Nombre de résultats à retourner
            
        Returns:
            Liste de tuples (indice, score) pour les chunks les plus pertinents
        """
        if self.tfidf_matrix is None or not hasattr(self.tfidf_vectorizer, 'vocabulary_'):
            return []
        
        try:
            # Transformer la requête en vecteur TF-IDF
            query_vec = self.tfidf_vectorizer.transform([query])
            
            # Calculer la similarité entre la requête et tous les chunks
            # Utiliser la similarité cosinus via le produit de matrices
            similarity = query_vec.dot(self.tfidf_matrix.T).toarray()[0]
            
            # Trouver les top_k indices avec les scores les plus élevés
            top_indices = similarity.argsort()[-top_k:][::-1]
            top_scores = similarity[top_indices]
            
            # Retourner les paires (indice, score)
            return [(int(idx), float(score)) for idx, score in zip(top_indices, top_scores)]
            
        except Exception as e:
            # logger.error(f"Erreur lors de la recherche lexicale: {str(e)}")
            return []

    def _normalize_scores(self, scores_list: List[Tuple[int, float]]) -> Dict[int, float]:
        """
        Normalise les scores pour qu'ils soient entre 0 et 1.
        
        Args:
            scores_list: Liste de tuples (indice, score)
            
        Returns:
            Dictionnaire {indice: score normalisé}
        """
        scores_dict = {}
        
        if not scores_list:
            return scores_dict
        
        # Extraire les scores
        scores = [score for _, score in scores_list]
        
        # Trouver min et max pour la normalisation
        min_score = min(scores)
        max_score = max(scores)
        
        # Éviter la division par zéro
        if min_score == max_score:
            # Tous les scores sont identiques
            for idx, _ in scores_list:
                scores_dict[idx] = 1.0
        else:
            # Normalisation min-max
            for idx, score in scores_list:
                normalized_score = (score - min_score) / (max_score - min_score)
                scores_dict[idx] = normalized_score
        
        return scores_dict

    def _merge_search_results(self, semantic_results: List[Tuple[int, float]], 
                             lexical_results: List[Tuple[int, float]], 
                             hybrid_weight: float, 
                             top_k: int) -> List[Dict[str, Any]]:
        """
        Fusionne les résultats de recherche sémantique et lexicale avec pondération.
        
        Args:
            semantic_results: Résultats de la recherche sémantique [(indice, score)]
            lexical_results: Résultats de la recherche lexicale [(indice, score)]
            hybrid_weight: Poids de la recherche sémantique (0 à 1)
            top_k: Nombre de résultats à retourner
            
        Returns:
            Liste des chunks les plus pertinents avec scores fusionnés
        """
        # Normaliser les scores sémantiques
        semantic_scores = self._normalize_scores(semantic_results)
        
        # Normaliser les scores lexicaux
        lexical_scores = self._normalize_scores(lexical_results)
        
        # Fusionner les scores avec pondération
        combined_scores = {}
        
        # Ajouter les scores sémantiques pondérés
        for idx, score in semantic_scores.items():
            combined_scores[idx] = score * hybrid_weight
        
        # Ajouter les scores lexicaux pondérés
        for idx, score in lexical_scores.items():
            if idx in combined_scores:
                combined_scores[idx] += score * (1 - hybrid_weight)
            else:
                combined_scores[idx] = score * (1 - hybrid_weight)
        
        # Trier les résultats par score
        sorted_results = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Prendre les top_k meilleurs résultats
        top_results = sorted_results[:top_k]
        
        # Préparer les résultats finaux
        results = []
        for i, (idx, score) in enumerate(top_results):
            if idx < len(self.chunks) and idx >= 0:  # Vérification d'index valide
                chunk = self.chunks[idx]
                results.append({
                    "chunk": chunk,
                    "text": chunk["text"],
                    "doc_id": chunk["doc_id"],
                    "score": score,
                    "rank": i
                })
        
        return results

    def search(self, query: str, top_k: int = 5, hybrid_weight: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Recherche les chunks les plus pertinents pour une requête.
        Utilise une recherche hybride (sémantique + lexicale) si activée.
        
        Args:
            query: Requête de recherche
            top_k: Nombre de résultats à retourner
            hybrid_weight: Poids de la recherche sémantique (0 à 1, None = utiliser self.semantic_weight)
            
        Returns:
            Liste des chunks les plus pertinents avec scores et métadonnées
        """
        if self.index is None or not self.chunks:
            # logger.error("Aucun document n'a été indexé. Impossible d'effectuer la recherche.")
            return []
        
        # Utiliser le poids par défaut si non spécifié
        if hybrid_weight is None:
            hybrid_weight = self.semantic_weight
        
        # Générer l'embedding de la requête
        query_embedding = self._get_embeddings([query])[0].reshape(1, -1)
        
        # Vérifier si la recherche hybride est activée
        if self.hybrid_search and self.tfidf_matrix is not None:
            # Recherche sémantique
            semantic_results = self._search_semantic(query_embedding, top_k * 2)  # Récupérer plus de résultats pour le mélange
            
            # Recherche lexicale
            lexical_results = self._search_lexical(query, top_k * 2)
            
            #################################################
            # print("Semantic_results : ",semantic_results)
            # print("lexical_results : ",lexical_results)

            # Fusionner les résultats avec pondération
            return self._merge_search_results(semantic_results, lexical_results, hybrid_weight, top_k)
        else:
            # Recherche sémantique uniquement
            semantic_results = self._search_semantic(query_embedding, top_k)
            
            # Préparer les résultats
            results = []
            for i, (idx, score) in enumerate(semantic_results):
                if idx < len(self.chunks) and idx >= 0:  # Vérification d'index valide
                    chunk = self.chunks[idx]
                    results.append({
                        "chunk": chunk,
                        "text": chunk["text"],
                        "doc_id": chunk["doc_id"],
                        "score": score,
                        "rank": i
                    })
            
            return results

    def get_relevant_context(self, query, top_k=None, hybrid_weight=None, add_first_chunk=False) -> str:
        """
        Obtient un contexte pertinent pour une requête en combinant les meilleurs chunks.
        
        Args:
            query: Requête de recherche
            top_k: Nombre de chunks à utiliser (utilise self.retrieval_top_k si None)
            hybrid_weight: Poids de la recherche sémantique (None = utiliser self.semantic_weight)
            
        Returns:
            Contexte pertinent (chunks combinés)
        """
        # Utiliser la valeur par défaut si top_k n'est pas spécifié
        if top_k is None:
            top_k = self.retrieval_top_k
        
        try:
            # Appel à search avec le nouveau paramètre hybrid_weight
            results = self.search(query, top_k, hybrid_weight)
            
            if not results:
                if self.documents:
                    # Renvoyer le début du premier document si aucun résultat
                    doc_id = list(self.documents.keys())[0]
                    return self.documents[doc_id][:3000]
                return ""
            
            # Trier les résultats par doc_id et position dans le document
            results.sort(key=lambda x: (x["chunk"]["doc_id"], x["chunk"]["start_char"]))
            
            # Joindre les chunks
            relevant_chunks = [result["text"] for result in results]
            
            # Ajouter le début du document si le premier chunk n'est pas dans les résultats
            if add_first_chunk:
                first_doc_id = results[0]["chunk"]["doc_id"]
                first_chunk_found = any(r["chunk"]["chunk_id"] == f"{first_doc_id}_0" for r in results)
                if not first_chunk_found and first_doc_id in self.documents:
                    first_chunk = self._split_text_into_chunks(self.documents[first_doc_id], first_doc_id)[0]["text"]
                    relevant_chunks.insert(0,first_chunk)
            
            # Joindre les chunks pertinents
            context = "\n\n---------------------------------\n\n".join(relevant_chunks)
            
            # Limiter la taille du contexte pour éviter des prompts trop longs
            max_context_length = self.max_car
            if len(context) > max_context_length:
                context = context[:max_context_length]
                
            return context
            
        except Exception as e:
            # logger.error(f"Erreur dans get_relevant_context: {str(e)}")
            import traceback
            # logger.error(f"Stack trace: {traceback.format_exc()}")
            
            # Fallback en cas d'erreur: retourner le début du premier document disponible
            if self.documents:
                doc_id = list(self.documents.keys())[0]
                return self.documents[doc_id][:3000]
            return ""

    def process_document(self, dfAttributes: pd.DataFrame, doc_id: str, hybrid_weight: Optional[float] = None) -> Dict[str, Any]:
        """
        Traite un document pour extraire toutes les informations demandées.
        
        Args:
            doc_id: Identifiant du document
            hybrid_weight: Poids de la recherche sémantique (None = utiliser self.semantic_weight)
            
        Returns:
            Dictionnaire avec les informations extraites
        """
        # logger.info(f"Traitement du document {doc_id}...")
        
        if doc_id not in self.documents:
            # logger.error(f"Document {doc_id} non trouvé dans la base de documents.")
            return {
                "titre": "Document non trouvé",
                "objet du marché": "",
                "Résumé des prestations": "",
                "allotissement": False,
                "titres des lots": "Nan"
            }
        
        try:
            # result = {}
            # logger.info("Extraction du titre...")
            chunks_list = []
            cpt = 0
            for idx, row in dfAttributes.iterrows():
                search = row['search']
                if cpt==0:
                    chunks_list.append(self.get_relevant_context(search, hybrid_weight=hybrid_weight, add_first_chunk=True))
                else:
                    chunks_list.append(self.get_relevant_context(search, hybrid_weight=hybrid_weight))
                cpt+=1
            result = '\n'.join(chunks_list)
            # logger.info(f"Traitement du document {doc_id} terminé.")
            return result
            
        except Exception as e:
            # logger.error(f"Erreur lors du traitement du document {doc_id}: {str(e)}")
            # Tracer la stack trace pour aider au débogage
            import traceback
            # logger.error(f"Stack trace: {traceback.format_exc()}")
            
            # Retourner un résultat d'erreur
            return {
                "titre": f"ERREUR: {str(e)[:100]}...",
                "objet du marché": "",
                "Résumé des prestations": "",
                "allotissement": False,
                "titres des lots": "Nan"
            }


def df_select_content(dfFiles: pd.DataFrame, 
                      dfAttributes: pd.DataFrame,
                      max_mots=5000,
                      api_key="",
                      base_url="",
                      embedding_model="BAAI/bge-m3",
                      chunk_size=1000,
                      chunk_overlap=200,
                      hybrid_search=True,
                      semantic_weight=0.7,
                      retrieval_top_k=3,
                      max_workers=5,
                      save_path=None, 
                      directory_path=None,
                      save_grist=False) -> pd.DataFrame:
    """
    Sélectionne le contenu pertinent du texte s'il est trop volumineux sinon renvoie tout le texte dans le DataFrame.
    
    Args:
        dfFiles (DataFrame): DataFrame avec les colonnes 'text', 'is_OCR', 'nb_mot'
        
    Returns:
        DataFrame: DataFrame avec les colonnes 'relevant_content', 'is_embedded' ajoutées
    """
    dfResult = dfFiles.copy(deep=False)

    dfResult['relevant_content'] = dfResult['text']
    dfResult['is_embedded'] = False

    
    # Traiter le DataFrame pour extraire le contexte
    # for index, row in dfResult.query(f"nb_mot > {max_mots}").iterrows():
    def process_row(idx):    
        doc_id = idx
        text = dfResult.at[idx, 'text']
        rag_env = RAGEnvironment(
            api_key=api_key,
            base_url=base_url,
            embedding_model=embedding_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            hybrid_search=hybrid_search,
            semantic_weight=semantic_weight,
            retrieval_top_k=retrieval_top_k,
            max_car=max_mots
        )

        # Réinitialiser pour chaque document
        rag_env.documents = {}
        rag_env.chunks = []
        rag_env.index = None
        rag_env.tfidf_matrix = None

        rag_env.add_documents({doc_id: text})

        try: 
            dfSpecAttributes = select_attr(dfAttributes, dfResult.at[idx, 'classification'])
        except Exception as e:
            print("Erreur dans la récupération des attributs :", e, dfResult.loc[idx])

        # Traiter le document
        try:
            result = {
                'relevant_content': rag_env.process_document(doc_id=doc_id, dfAttributes=dfSpecAttributes, hybrid_weight=semantic_weight),
                'is_embedded': True # Marquer comme traité avec embedding
            }
        except Exception as e:
            print(e)
    
        return idx, result

    # Appliquer le traitement en parallèle pour chaque ligne du DataFrame
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_row, idx): idx for idx in dfResult.query(f"nb_mot > {max_mots}").index}
        for future in tqdm(futures, total=len(futures), desc="Traitement des documents"):
            idx, result = future.result()
            for key, value in result.items():
                dfResult.at[idx, key] = value

    try:
        if(save_grist):
            update_records_in_grist(dfResult, 
                              key_column='filename', 
                              table_url=URL_TABLE_ATTACHMENTS,
                              api_key=API_KEY_GRIST,
                              columns_to_update=['relevant_content', 'is_embedded'],
                              batch_size=30)
    
        
        if(save_path != None):
            dfResult.to_csv(f'{save_path}/contentselected_{directory_path.split("/")[-1]}_{getDate()}.csv', index = False)
            print(f"Liste des fichiers sauvegardées dans {save_path}/contentselected_{directory_path.split("/")[-1]}_{getDate()}.csv")

    except Exception as e:
        print(f"Erreur lors de la sauvegarde du DataFrame : {e}")

    return dfResult


def save_df_select_content_result(df: pd.DataFrame):
    # Clean NUL bytes from text columns before saving to PostgreSQL
    from app.utils import clean_nul_bytes_from_dataframe
    df_clean = clean_nul_bytes_from_dataframe(df, ['relevant_content'])
    bulk_update_attachments(df_clean, ['relevant_content', 'is_embedded'])
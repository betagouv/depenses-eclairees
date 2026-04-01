# Glossaire

| Terme | Définition |
|---|---|
| **AIFE** | Agence pour l'Informatique Financière de l'État. Maîtrise d'ouvrage du projet Chorus. |
| **Albert** | API LLM souveraine opérée par la DINUM, basée sur les modèles Mistral. Utilisée pour la classification, l'extraction structurée et l'OCR. |
| **API OData** | Protocole REST utilisé par l'API de synchronisation Chorus/SAP pour exposer les engagements juridiques et pièces jointes. |
| **Aptfile** | Fichier Scalingo listant les paquets système à installer (Tesseract, LibreOffice). |
| **BetaGouv** | Programme d'incubation de services numériques de l'État. Dépenses Éclairées est un produit BetaGouv. |
| **BIC** | Bank Identifier Code — identifiant bancaire international (8 ou 11 caractères). |
| **BOAMP** | Bulletin Officiel des Annonces de Marchés Publics. |
| **BPU** | Bordereau de Prix Unitaires — document listant les prix par unité d'œuvre. |
| **CAO** | Commission d'Appel d'Offres. |
| **CCAG** | Cahier des Clauses Administratives Générales — conditions standard des marchés publics. |
| **CCAP** | Cahier des Clauses Administratives Particulières — conditions spécifiques d'un marché. |
| **CCTP** | Cahier des Clauses Techniques Particulières — spécifications techniques d'un marché. |
| **Celery** | Framework Python de file d'attente de tâches distribuées. Utilisé pour l'exécution parallèle du pipeline. |
| **Chorus** | Système d'information financière de l'État (SAP). Gestion des engagements juridiques et des paiements. |
| **Classification** | Étape 2 du pipeline : le LLM attribue une catégorie au document parmi ~50 catégories. |
| **Content analysis** | Étape 3 du pipeline : le LLM extrait des données structurées du document. |
| **CPV** | Common Procurement Vocabulary — classification européenne des marchés publics. |
| **DC1** | Lettre de candidature (formulaire marchés publics). |
| **DC4** | Déclaration de sous-traitance (formulaire marchés publics). |
| **DINUM** | Direction Interministérielle du Numérique. Opère l'API Albert. |
| **DPGF** | Décomposition du Prix Global et Forfaitaire. |
| **DQE** | Détail Quantitatif Estimatif. |
| **DSFR** | Design Système de l'État Français — framework UI officiel des services publics numériques. |
| **EJ** | Engagement Juridique — acte par lequel l'État s'engage à payer une dépense. Identifié par un `num_ej`. |
| **Grist** | Base de données collaborative open-source. Utilisée pour les données de vérité terrain (tests e2e) et les métriques. |
| **IBAN** | International Bank Account Number — identifiant de compte bancaire (27 caractères pour la France, commence par FR). |
| **JSON Schema** | Standard de description de structure JSON. Utilisé comme `response_format` pour contraindre les réponses du LLM. |
| **LLM** | Large Language Model — modèle de langage. Ici, Mistral via l'API Albert. |
| **Mistral** | Éditeur des modèles d'IA utilisés par Albert (`openweight-medium` (alias Albert pour `mistral-small`), `mistral-medium-2508`, `mistral-ocr-2512`). |
| **OCR** | Optical Character Recognition — reconnaissance de caractères dans les images/scans. |
| **ORM** | Object-Relational Mapping — couche d'abstraction Django pour la base de données. |
| **PJ** | Pièce Jointe — document rattaché à un engagement juridique. |
| **Procfile** | Fichier Scalingo définissant les processus (web, workers, cron). |
| **ProConnect** | Service d'authentification de l'État (OpenID Connect), opéré par La Suite numérique. |
| **PyMuPDF** | Bibliothèque Python pour manipuler les fichiers PDF (extraction texte, rendu image). |
| **RateGate** | Mécanisme de rate limiting distribué basé sur PostgreSQL, utilisé pour espacer les appels LLM entre workers Celery. |
| **Redis** | Base de données in-memory utilisée comme broker de messages Celery. |
| **Response format** | Paramètre de l'API LLM qui contraint la réponse à un schéma JSON. |
| **RIB** | Relevé d'Identité Bancaire — document contenant les coordonnées bancaires. |
| **SAP** | Systems, Applications and Products — éditeur du logiciel Chorus. |
| **SAP BTP** | SAP Business Technology Platform — plateforme cloud SAP. |
| **Scalingo** | PaaS (Platform as a Service) français. Héberge l'application Dépenses Éclairées. |
| **schwifty** | Bibliothèque Python de validation IBAN (ISO 13616). |
| **SIREN** | Numéro d'identification d'une entreprise (9 chiffres). |
| **SIRET** | Numéro d'identification d'un établissement (14 chiffres = SIREN + NIC). |
| **structured_data** | Champ JSON du modèle `Document` contenant les informations extraites et nettoyées. |
| **Tesseract** | Moteur OCR open-source (Google). Utilisé localement pour les images. |
| **Text extraction** | Étape 1 du pipeline : extraction de texte brut à partir du fichier (PDF, DOCX, etc.). |
| **Vue 360°** | Interface web Django/DSFR permettant de consulter toutes les informations d'un engagement juridique et ses documents. |

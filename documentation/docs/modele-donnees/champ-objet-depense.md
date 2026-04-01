# Champ "objet de la dépense"

## Définition fonctionnelle

L'**objet de la dépense** est l'information principale extraite des documents : il décrit **ce qui a été acheté** ou le service fourni. C'est le champ le plus visible dans la vue 360° et le plus critique pour la compréhension d'un engagement juridique.

## Nommage par type de document

L'objet est extrait sous **différents noms** selon le type de document :

| Type document | Champ JSON | Consigne résumée | Source |
|---|---|---|---|
| `acte_engagement` | `objet_marche` | Objet du marché | `attributes/acte_engagement.py` |
| `ccap` | `objet_marche` | Formulation synthétique de l'objet | `attributes/ccap.py` |
| `fiche_navette` | `objet` | Objet de la commande ou du marché | `attributes/fiche_navette.py` |
| `devis` | `objet` | Objet métier du devis | `attributes/devis.py` |
| `bon_de_commande` | `objet` | Objet de la commande | `attributes/bon_de_commande.py` |
| `avenant` | `objet` | Objet de la commande | `attributes/avenant.py` |
| `sous_traitance` | `objet_marche` | Formulation synthétique de l'objet | `attributes/sous_traitance.py` |
| `rib` | — | Pas d'objet extrait | — |
| `kbis` | — | Pas d'objet extrait | — |
| `att_sirene` | — | Pas d'objet extrait | — |

## Règles d'extraction communes

Extraites verbatim des consignes des prompts :

1. **Ne pas inclure le type de document** : « Devis pour ... » → enlever « Devis pour »
2. **Avoir du sens pour un tiers** : l'objet doit être compréhensible par une personne extérieure
3. **Ne rien renvoyer si absent** : `null` ou `""` si aucun objet trouvé
4. **Reformuler si incompréhensible** : proposer un objet simple reflétant le contenu

## Cas spécial : devis avec raisonnement

Le type `devis` ajoute un champ `raisonnement` qui documente **comment** l'objet a été obtenu :

| Scénario | Valeur du raisonnement |
|---|---|
| Objet trouvé explicitement | « Objet présent dans le document (extrait de la mention ...) » |
| Objet inféré des prestations | « Objet inféré à partir des prestations / lignes du tableau : ... » |
| Objet introuvable | « Objet non trouvé ; inférence impossible ou trop vague » |

Ce mécanisme de traçabilité est **unique au type devis** et n'existe pas pour les autres types.

## Agrégation au niveau EJ

Les champs `DataEngagement.designation` et `DataEngagement.descriptif_prestations` existent sur le modèle, mais :

!!! warning "Champs non peuplés automatiquement"

    L'agrégation de l'objet au niveau de l'engagement juridique (depuis les `structured_data` des documents rattachés) **n'a pas été observée dans le pipeline actuel**. Ces champs sont `null=True` et semblent remplis par un autre processus (sync API ou manuel).

Le champ `DataEngagement.sources_et_conflits` (JSON) pourrait servir à tracer les conflits entre objets extraits de différents documents d'un même EJ, mais son utilisation n'a pas été vérifiée.

**Source** : `docia/file_processing/processor/attributes/*.py`, `docia/documents/models.py`

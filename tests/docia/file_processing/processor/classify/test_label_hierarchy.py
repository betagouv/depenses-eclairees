from docia.file_processing.processor.classify.label_hierarchy import (
    COARSE_ANNEXE,
    COARSE_CATALOGUE_PRIX,
    COARSE_CERTIFICATS_ADMINISTRATIFS,
    COARSE_CONTRATS_MIXTE,
    COARSE_DOSSIER_CANDIDATURE,
    COARSE_EXECUTION_COMMANDE,
    COARSE_MESSAGERIE,
    COARSE_OUTIL_GESTION,
    COARSE_RIB,
    map_llm_to_coarse,
)


def test_annexe_isolates_cc_cap_ctp_annexes_only():
    assert map_llm_to_coarse("ccap_annexe") == COARSE_ANNEXE
    assert map_llm_to_coarse("cctp_annexe") == COARSE_ANNEXE
    assert map_llm_to_coarse("ccap_annexe_beneficiaires") == COARSE_ANNEXE
    assert map_llm_to_coarse("ae_annexe") == COARSE_CATALOGUE_PRIX


def test_acte_engagement_only_itself():
    assert map_llm_to_coarse("acte_engagement") == "acte_engagement"
    assert map_llm_to_coarse("ae_annexe") != "acte_engagement"


def test_catalogue_prix_covers_financial_and_legacy_aliases():
    assert map_llm_to_coarse("bordereau_prix") == COARSE_CATALOGUE_PRIX
    assert map_llm_to_coarse("annexe_financiere") == COARSE_CATALOGUE_PRIX
    assert map_llm_to_coarse("offre_commerciale") == COARSE_CATALOGUE_PRIX
    assert map_llm_to_coarse("devis") == "devis"
    assert map_llm_to_coarse("facture") is None


def test_messagerie_and_contrats_mixte():
    assert map_llm_to_coarse("mail") == COARSE_MESSAGERIE
    assert map_llm_to_coarse("ccc") == COARSE_CONTRATS_MIXTE
    assert map_llm_to_coarse("conv_financement") == COARSE_CONTRATS_MIXTE


def test_ccp_identity_and_mitigations_nov_2026():
    assert map_llm_to_coarse("ccp_simple") == "ccp_simple"
    assert map_llm_to_coarse("ccp_vae") == "ccp_vae"
    assert map_llm_to_coarse("fiche_achat") == COARSE_EXECUTION_COMMANDE
    assert map_llm_to_coarse("application_revision_prix") == COARSE_EXECUTION_COMMANDE
    assert map_llm_to_coarse("reconduction") == COARSE_EXECUTION_COMMANDE
    assert map_llm_to_coarse("ca_chgt_rib") == COARSE_RIB
    assert map_llm_to_coarse("ca_chgt_ej") == COARSE_CERTIFICATS_ADMINISTRATIFS
    assert map_llm_to_coarse("delegation_pouvoir") == COARSE_CERTIFICATS_ADMINISTRATIFS
    assert map_llm_to_coarse("rapport_signature") == COARSE_OUTIL_GESTION
    assert map_llm_to_coarse("fiche_engagement") == COARSE_OUTIL_GESTION
    assert map_llm_to_coarse("lettre_candidature_dc1") == COARSE_DOSSIER_CANDIDATURE
    assert map_llm_to_coarse("fiche_navette") == "fiche_navette"
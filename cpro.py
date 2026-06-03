import logging
import optparse
import os
import platform
import sys
import time
from datetime import datetime, timedelta, date

from cloakbrowser import launch, launch_context

logger = logging.getLogger(__name__)

# Determine select-all keyboard shortcut based on OS
SELECT_ALL_MODIFIER = "Meta" if platform.system() == "Darwin" else "Control"


def parse_args():
    parser = optparse.OptionParser()
    parser.add_option("--start", dest="start", help="Start date in ISO format (YYYY-MM-DD)")
    parser.add_option("--end", dest="end", help="End date in ISO format (YYYY-MM-DD)")
    parser.add_option("--scope", dest="scope", help="Scope code")
    parser.add_option("--headed", action="store_true", default=False, help="Run in headed mode")
    parser.add_option("--provider-name", dest="provider_name", help="Provider name (required if provider is specified)")
    parser.add_option("--provider-siret", dest="provider_siret", help="Provider SIRET (mutually exclusive with --provider-siren)")
    parser.add_option("--provider-siren", dest="provider_siren", help="Provider SIREN (mutually exclusive with --provider-siret)")
    parser.add_option("--num-ej", dest="num_ej", help="Numéro EJ (Bon de commande)")
    options, args = parser.parse_args()
    return options


def init_context(headless: bool = True):
    """Initialize browser context with cookies and download handler."""
    logger.info("Initializing context...")
    os.makedirs("../downloads", exist_ok=True)
    ctx = launch_context(headless=headless)
    ctx.add_cookies([
        { "name": "JSESSIONID",
          "value": os.environ["JSESSIONID"],
          "domain": "cpro.chorus-pro.gouv.fr",
          "path": "/cpp",
        },
    ])
    page = ctx.new_page()
    logger.info("Context initialized.")
    return ctx, page


def init_search_page(page, scope: str):
    """Navigate to the invoice search page and fill the static form criteria."""
    logger.info(f"Initializing search page for scope={scope}")
    page.goto("https://cpro.chorus-pro.gouv.fr/cpp/rechercheFactures")
    page.select_option("select[name='listeResultats.critere.structureDestinataireId']", value="568055")
    page.click("#GFR_RechercheFacturesRecues_Criteres_BtnRechercherService")
    page.fill("input[name='listeServices.critere.code']", scope)
    page.click("button[type='submit']")
    page.click("#selection0")
    page.select_option("select[name='listeResultats.critere.etatCourant']", value="MISE_EN_PAIEMENT")
    logger.info("Search page initialized.")


def fill_provider(page, provider_name: str, provider_siret: str = None, provider_siren: str = None):
    """Fill the provider search field. Requires either siret or siren (but not both) and a name.
    
    Args:
        page: The Playwright page object
        provider_name: The name of the provider (required)
        provider_siret: The SIRET of the provider (optional, mutually exclusive with provider_siren)
        provider_siren: The SIREN of the provider (optional, mutually exclusive with provider_siret)
    """
    if provider_siret and provider_siren:
        raise ValueError("Cannot provide both siret and siren. Please provide only one.")
    if not provider_siret and not provider_siren:
        raise ValueError("Must provide either siret or siren.")
    
    identifier = provider_siret or provider_siren
    logger.info(f"Filling provider: name={provider_name}, identifier={identifier}")
    
    # Click on the provider select2 container to open the dropdown
    page.click("#select2-GFR_RechercheFacturesRecues_Criteres_StructureFournisseurGFR_RechercheFacturesRecues-container")
    
    # Type the siret or siren
    page.keyboard.type(identifier)
    
    # Wait for results and click the first one
    page.click("#select2-GFR_RechercheFacturesRecues_Criteres_StructureFournisseurGFR_RechercheFacturesRecues-results li:first-child")
    
    # If siren is provided, check if SIREN checkbox is disabled and enable it if needed
    if provider_siren:
        siren_checkbox = page.locator("#TRA_Recherche_Factures_Coche_SIREN")
        is_disabled = siren_checkbox.get_attribute("disabled")
        if is_disabled:
            logger.info("SIREN checkbox is disabled, enabling it...")
            page.evaluate("""() => {
                const el = document.getElementById('TRA_Recherche_Factures_Coche_SIREN');
                if (el) el.disabled = false;
            }""")
        # Click the label to select SIREN
        page.click("label[for='TRA_Recherche_Factures_Coche_SIREN']")
    
        # Assert that SIREN checkbox is checked
        assert page.locator("#TRA_Recherche_Factures_Coche_SIREN").is_checked(), "SIREN checkbox should be checked"
        assert page.input_value("input[name='rechercheParSiren']") == "true", "rechercheParSiren should be true"
    
    logger.info(f"Provider filled successfully: {provider_name}")


def fill_num_ej(page, num_ej: str):
    """Fill the numéro bon de commande (EJ) field.
    
    Args:
        page: The Playwright page object
        num_ej: The numéro EJ (bon de commande) to fill
    """
    logger.info(f"Filling numéro EJ: {num_ej}")
    page.fill("input[name='listeResultats.critere.numeroBonDeCommande']", num_ej)
    logger.info(f"Numéro EJ filled successfully: {num_ej}")


def fill_date(page, date: date):
    """Fill the date fields with the specified date.
    
    Args:
        page: The Playwright page object
        date: The date to fill in the form
    """
    str_date = date.strftime("%d/%m/%Y")
    logger.info(f"Filling date: {date}")
    page.click("[data-target='#GDP_RechercheFacture_CriteresPanneau_Body']")
    page.locator("#GFR_RechercheFactureEtatAcompteRecus_Criteres_BoutonRechercher").scroll_into_view_if_needed()
    page.click("input[name='listeResultats.critere.dateHeureEtatCourantDebut']")
    page.keyboard.press(f"{SELECT_ALL_MODIFIER}+a")
    page.keyboard.type(str_date)
    page.click("input[name='listeResultats.critere.dateHeureEtatCourantFin']")
    page.keyboard.press(f"{SELECT_ALL_MODIFIER}+a")
    page.keyboard.type(str_date)


def load(page):
    """Submit the search form by clicking the search button.
    
    Args:
        page: The Playwright page object
    """
    logger.info("Submitting search form...")
    page.click("#GFR_RechercheFactureEtatAcompteRecus_Criteres_BoutonRechercher")
    page.wait_for_load_state("load")
    logger.info("Search form submitted.")


def check_form_arguments(page, str_date: str):
    """Verify that the form fields have the expected values.

    Args:
        page: The Playwright page object
        str_date: The date string in DD/MM/YYYY format
    """
    assert page.input_value("input[name='listeResultats.critere.dateHeureEtatCourantDebut']") == str_date
    assert page.input_value("input[name='listeResultats.critere.dateHeureEtatCourantFin']") == str_date


def load_date(page, date: date) -> bool:
    """Fill the date fields and trigger search for a specific date.
    Returns False if no results found, True otherwise."""
    str_date = date.strftime("%d/%m/%Y")
    logger.info(f"Loading data for date={date}")
    fill_date(page, date)
    load(page)
    check_form_arguments(page, str_date)
    
    # Check if table with "Résultats de la recherche" caption exists (indicates results were found)
    if page.query_selector("table caption:has-text('Résultats de la recherche')") is None:
        logger.info("No results found for this date.")
        return False
    return True


def go_next_page(page) -> bool:
    """Check for a next page button and click it if available. Returns True if a new page was loaded, False otherwise."""
    next_button = page.locator("button[title='Aller à la page suivante du tableau']")
    is_disabled = next_button.get_attribute("disabled")
    if is_disabled:
        logger.info("No next page available.")
        return False
    
    logger.info("Navigating to next page...")
    next_button.click()
    page.wait_for_load_state("load")
    logger.info("Next page loaded.")
    return True


def download_items(page, date: date, scope: str, provider_name: str = None):
    """Select all items on the current page and trigger bulk download.
    
    Args:
        page: The Playwright page object
        date: The date being processed
        scope: The scope code
        provider_name: Optional provider name to include in filename
    """
    # Get current page number from value attribute of the active page button
    page_button = page.locator("li.paginate__page.paginate__page_active button[name='listeResultats.page']")
    page_number = page_button.get_attribute("value")
    
    date_file = date.strftime("%Y%m%d")
    if provider_name:
        # Sanitize provider name for filename (remove special characters and spaces)
        safe_provider = "".join(c if c.isalnum() else "_" for c in provider_name)
        filename = f"{scope}_{safe_provider}_{date_file}_{page_number}.zip"
    else:
        filename = f"{scope}_{date_file}_{page_number}.zip"
    filepath = f"../downloads/{filename}"
    
    if os.path.exists(filepath):
        logger.info(f"File {filename} already exists, skipping download for scope={scope}, date={date}, page={page_number}")
        return
    
    # Verify date fields have the expected values
    str_date = date.strftime("%d/%m/%Y")
    assert page.input_value("input[name='listeResultats.critere.dateHeureEtatCourantDebut']") == str_date
    assert page.input_value("input[name='listeResultats.critere.dateHeureEtatCourantFin']") == str_date
    
    logger.info(f"Downloading items for scope={scope}, date={date}, page={page_number}")

    checkbox = page.locator("#actualiserDEFAULT-1")
    checkbox.locator("xpath=ancestor::span").click()
    page.click("#Synthese_Btn_TelechargerEnMasse")

    with page.expect_download(timeout=5 * 60 * 1000) as download_info:
        page.click("#GDP_Telechargementfacture_BoutonTelecharger")
    download = download_info.value
    assert download_info.is_done(), "Download should be done."
    download.save_as(filepath)
    logger.info(f"Saved as {filename}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    options = parse_args()
    start_date = date.fromisoformat(options.start)
    end_date = date.fromisoformat(options.end)
    scope = options.scope
    
    # Parse provider options
    provider_name = options.provider_name
    provider_siret = options.provider_siret
    provider_siren = options.provider_siren
    
    # Validate provider options
    has_provider = provider_name or provider_siret or provider_siren
    if has_provider:
        if not provider_name:
            raise ValueError("Provider name is required when specifying a provider. Use --provider-name.")
        if not provider_siret and not provider_siren:
            raise ValueError("Must provide either --provider-siret or --provider-siren when specifying a provider.")
        if provider_siret and provider_siren:
            raise ValueError("Cannot provide both --provider-siret and --provider-siren. Please provide only one.")
    
    try:
        ctx, page = init_context(headless=not options.headed)
        
        # Initialize search page once
        init_search_page(page, scope)
        
        # Fill provider if specified
        if has_provider:
            fill_provider(page, provider_name, provider_siret, provider_siren)
        
        # Fill numéro EJ if specified
        if options.num_ej:
            fill_num_ej(page, options.num_ej)
        
        # Loop through all dates from start to end (inclusive)
        current_date = start_date
        while current_date <= end_date:
            logger.info(f"Starting download for scope={scope}, date={current_date}")
            
            if not load_date(page, current_date):
                logger.info(f"Skipping date {current_date} - no results found.")
                current_date += timedelta(days=1)
                continue
            
            # Download all pages for this date
            while True:
                download_items(page, current_date, scope, provider_name)
                if not go_next_page(page):
                    break
            
            current_date += timedelta(days=1)
        
        input(">>")
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        logger.info("Closing context...")
        ctx.close()
        logger.info("Context closed.")
